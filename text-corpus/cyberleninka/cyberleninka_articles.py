""" Cyberleninka articles Downloader
Date:       26.04.2019

https://github.com/yarchiksmith/cyberleninka-parser

str2id workaround
https://python.devhelping.com/article/20790976/Python+shortest+unique+id+from+strings

####

Usage examples:
===============
1. Save up to 40 posts that has a tag `ООП`:

py cylen_articles.py -q "[ООП]" --limit 40

2. Save all posts that relevant to `ООП`:

py cylen_articles.py -q "ООП"


Requirements:
=============
- Python 3
- requests          (pip install requests)
- beautifulsoup4    (pip install beautifulsoup4)


# Скрипт принимает 2 параметра:
# -q  –  query, поисковый запрос к Хабру
# -l  –  limit, лимит на число взятых пунктов из поиска


Если файл c поиском уже существует, он будет не перезаписан, а переименован в `имя (1)`, `имя (2)`, ...
Если после очистке строки запроса от спецсимволов имя файла совпадёт с существущим, он также будет переименован.

# Загрузка статей из файлов обратно в память:
    with open('200394.pkl', mode='rb') as f:
         doc = pickle.load(f)

"""

import argparse
# import datetime
import hashlib
import os
import pickle
import re
from time import sleep
# import shutil
# import ssl
# from urllib.request import Request, urlopen
import urllib.parse

from bs4 import BeautifulSoup
import requests
# import transliterate

DOMEN = 'https://cyberleninka.ru'

# limit for names (with ext.) of files to be saved
MAX_FILENAME_LENGTH = 60
HASH_ID_LEN = 8  # len of hash-like ID for converting human-readable ID (hrid)
CTRL_C_TIMEOUT = 3 # seconds to think after you hit Ctrl+C before execution continues

ARTICLES_DIR = 'articles/'
TOPIC_DIR = 'topic/'
SEARCH_DIR = 'search/'

# Опции для http-запросов:      (полезно про то, как писать веб-парсеры: https://python-scripts.com/requests-rules)
HEADERS = { 'User-Agent': 'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.137 YaBrowser/17.4.1.919 Yowser/2.5 Safari/537.36' }
TIMEOUT = 5 # seconds

def really_exit_by_Ctrl_C():
    "Console helper. Returns True if user pressed Ctrl+C again wihin the interval of `CTRL_C_TIMEOUT` seconds."
    print("\n^C")
    print("To break the process, Press Ctrl+C once again.")
    print("Waiting for",CTRL_C_TIMEOUT,"seconds...", end='\t', flush=True)
    try:
        sleep(CTRL_C_TIMEOUT)
    except KeyboardInterrupt:
        print("\n^C")
        print("Stopping...", end='\n'*2, flush=True)
        return True # exit, stop working
    print("continue...")
    print() # add newline
    return False # no exit, continue working

def parse_cmdline():
    """Parses command line arguments and returns an object with fields (of type string):
        query             (for -q option)
        limit             (for -l option)

    """
    parser = argparse.ArgumentParser(
        description='Download articles from Cyberleninka.ru'
    )
    parser.add_argument("--url", "-u",
                        help="webpage source full URL",
                        required=True)
    parser.add_argument("--type", "-t",
                        help="URL type: a - article page, c - category page, s - search page",
                        choices=['a','c','s'],
                        required=True)
    parser.add_argument("--query", "-q",
                        help="What to search and then download",
                        required=False)
    parser.add_argument("--limit", "-l",
                        default='0',
                        help="Save only first L articles from search results sorted by relevance, ignore others (default: no limit)",
                        required=False)
    # parser.add_argument("--log-file", "-l",
                        # default='./downloader-errors.log',
                        # help="[deprecated?] path to file used for logging errors (default: ./downloader-errors.log)",
                        # required=False)
    # parser.add_argument("--translit-names", "-t",
                        # default=False,
                        # help="translit cyrillic chars into latin in video file names (default: No)",
                        # action="store_true",
                        # required=False)
    args = parser.parse_args()

    netloc = urllib.parse.urlsplit(args.url).netloc
    DOMENnetloc = urllib.parse.urlsplit(DOMEN).netloc
    # print('netloc ', netloc)
    # print('DOMENnetloc ', DOMENnetloc)
    if not netloc:
        args.url = ''
    elif netloc.lower() != DOMENnetloc.lower():
        args.url = ''

    if args.url and args.type:
        if args.query:
            args.query = args.query.strip()
        args.limit = int(args.limit)
        # report parameters
        if args.type == 'a':
            mode = 'article'
        elif args.type == 'c':
            mode = 'category'
        else:
            mode = 'search'
        print('"Cyberleninka" articles Downloader started with parameters:')
        print(' URL type:          ', '`'+mode+'`'+' page')
        if args.query:
            print(' Search query:      ', '`'+args.query+'`')
        print(' max posts to save: ',args.limit)
        print(' Using URL:         ',args.url)
        # print(' Log file:       ',args.log_file)
        # print(' Translit names: ',args.translit_names)
        print()

    return args


def fit_filename(path, rename=False):
    """Makes path valid: removes unsuported chars and renames if such file exists. """
    dir, filename = os.path.split(path)
    name, ext = os.path.splitext(filename)

    # remove extra chars
    name = re.sub(r'(?:%\d+)|[^а-яёa-z\s\d.,!@#$%\(\)=+_-]+', r'', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'\s+',r'_', name)
    filename = name + ext

    # shrink filename if too long
    if(len(filename) > MAX_FILENAME_LENGTH):
        name = name[0:MAX_FILENAME_LENGTH-len(ext)]

    path = os.path.join(dir, name + ext)

    if not os.path.exists(path):
        return path

    # rename if exists  чтобы не затирать файл с таким же именем
    if rename:
        root, ext = os.path.splitext(path)
        count = 1
        while True:  # `do..while` emulation
            path = root + ' ('+str(count)+')' + ext
            if not os.path.exists(path):
                break
            count += 1

    return path


def prepare_dir(dir):
    """Checks the path and creates a directory if nesessary.
    If path does exist and is not a directory,
    or specified location is not writable, an exception is trown.

    """
    if not os.path.exists(dir):
        # create a directory tree
        try:
            os.makedirs(dir, exist_ok=True)
        except Exception as e:
            terminate_with_error(str(e) + '\n\tOccured while preparing dir:',dir)
        print('Dir created.')
    else:
        # check write permission
        if not os.access(dir, os.F_OK | os.W_OK):
            terminate_with_error("directory is not accessible or writable: "+dir)


def get_HTML_Page(url, query=''):
    """ Load page from URL """
    payload = None
    if query:
        # payload = {'q': query, 'target_type': 'posts', 'order_by': 'relevance', 'flow':''}
        payload = {'q': query}
        url = DOMEN + '/search'

    try:

        r = requests.get(url, params=payload, headers=HEADERS, timeout=TIMEOUT)

    except requests.ConnectionError as e:
        print("OOPS!! Connection Error. Make sure you are connected to Internet. Technical Details given below.\n")
        print(str(e))
        return
    except requests.Timeout as e:
        print("OOPS!! HTTP Timeout Error:")
        print(str(e))
        return
    except requests.RequestException as e:
        print("OOPS!! General HTTP Error:")
        print(str(e))
        return
    except KeyboardInterrupt:
        if really_exit_by_Ctrl_C():
            return
        else:
            print("Restarting interrupted saving of post",hrid,"...", flush=True)
            return get_HTML_Page(url, query) # recurse with same args

    # print(url + ' :\nPage load status_code =', r.status_code)   #для отладки
    if r.status_code != 200:
        return ""

    return r.text

# hrid : human readable ID
def save_cylen_article(url, overwrite=False, preview=None):
    """ Download (and save as pickle) a Cylen article with metadata (title, keywords, category, ...) """

    path = urllib.parse.urlsplit(url).path.split('/')
    path.reverse()    
    hrid = path[0]

    if not overwrite:
        # check if file already exists (i.e. full post has been saved before)
        # fname = os.path.join(ARTICLES_DIR, hrid + '.pkl')
        fname = os.path.join(ARTICLES_DIR, str2hexid(hrid) + '.pkl')
        if os.path.exists(fname):
            print('* post is already saved, skipping:',fname, flush=True)
            return # avoid to download duplicates

    # выгрузка документа
    print(' requesting article page "',hrid,'"...', sep='', end='\t \n', flush=True)
    # print('   full URL: ',url, flush=True)

    # HTML_Page = get_HTML_Page('https://cyberleninka.ru/article/n/' +hrid) #для отладки
    HTML_Page = get_HTML_Page(url)

    if not HTML_Page:
        print('  ... NO HTML page found!')
        return

    ### ОТЛАДКА > ###
    # with open('page.htm', 'w') as f:
        # f.write(HTML_Page)
    # print("### text saved.")
    ### < ОТЛАДКА ###

    # парсинг документа (это сделано в parse_Article_Page() )  :
    doc = parse_Article_Page(HTML_Page, preview)

    # with open('Article.txt', 'w') as f:         #для отладки
        # f.write(doc['text'])
    # print('  >>>>> Article saved to  "Article.txt"')

    doc_ok = doc['status'] == 'ok'
    doc['article-ID'] = hrid

    # сохранение результата в отдельный файл
    fail_prefix = '' if doc_ok else '-'
    fname = os.path.join(ARTICLES_DIR, fail_prefix + str2hexid(hrid) + '.pkl')

    with open(fname, 'wb') as f:
        pickle.dump(doc, f)
        f.seek(0, os.SEEK_END)  #размер открытого файла
        fsize = f.tell()
    # fsize = os.path.getsize(fname)  #так тоже можно (файл не открыт)

    # завершить строку с '...' кратким отчётом
    if doc_ok:
        print(fsize//1024,'Kb saved', '('+str(len(doc['text'])//1024), 'Kb of content,', len(HTML_Page)//1024,'Kb of html) OK\n')
    else:
        print('NO article found!')

    return

def parse_Article_Page(HTML_Text, preview=None):
    soup = BeautifulSoup(HTML_Text, "html.parser")   #, 'html5lib'  ('html5lib' - это отдельно устанавливаемая библиотека)

    doc = {}  # словарь с данными поста (статьи)
    doc_ok = False  # статус документа (False, если статья удалена)
    # doc['id'] = hrid

    allTags = soup.findAll("h2", {"class": "right-title"})
    for tag in allTags:
        if  "Текст научной работы" in tag.text:
            beginTag = tag
            doc_ok = True
            break

    if not doc_ok:
        # такое бывает, если статья не существовала или удалена
        doc['status'] = 'title_not_found'
        doc_ok = False
    else:
        doc['status'] = 'ok'
        doc['title'] = beginTag.find("span").text   # ищем внутри ТЕГА beginTag
        doc['title'] = re.search('«(.+)»', doc['title']).group(1)

        #Ищем Ключевые слова:
        doc['keywords'] = []
        keywordsTag = soup.find("div", {"class": "full keywords"})
        if keywordsTag:
            keywordsArr = keywordsTag.findAll("span")
            for tag in keywordsArr:
                doc['keywords'].append(tag.text)

        #Ищем Аннотацию:
        doc['abstract'] = ''
        abstractTag = soup.find("div", {"class": "full abstract"})
        if abstractTag:
            tag = abstractTag.find("p", {"itemprop":"description"})
            if tag:
                doc['abstract'] = tag.text

        article = soup.find("div", {"class": "ocr", "itemprop": "articleBody"})
        #Список литературы
        matchObj = re.search(r'СПИСОК ЛИТЕРАТУРЫ([\s\S]+)' + re.escape(doc['title']), article.text, flags=re.IGNORECASE)
        if matchObj:
            bibList = matchObj.group(1) #сейчас не используется
        # print(bibList)

        #Вырезаем все рекламные вставки
        allDivs = article.findAll("div")
        for t in allDivs:
            t.extract()

        #Вырезаем все Списки литературы, Заголовок и прочее
        articleText = ""
        for t in article.findAll("p"):
            t_Content = t.text

            if (re.search(r'^(\s*\d+\.\s+)+', t_Content.lstrip()) != None or
                re.search(r'СПИСОК ЛИТЕРАТУРЫ', t_Content, flags=re.IGNORECASE) or
                re.search(re.escape(doc['title']), t_Content, flags=re.IGNORECASE) ):
                t.extract()
            else:
                if len(t_Content) > 1 and t_Content[-1] == '-':
                    articleText += t_Content[:-1]   #соединяем Переносы
                else:
                    articleText += t_Content + '\n'

        if preview:  #Переносим данные из Словаря preview
            doc['number'] = preview['number']
            doc['topic'] = preview['topic']
            doc['url'] = preview['url']
            if preview["year"]:
                doc["year"] = preview["year"]
            if preview["Authors"]:
                doc["Authors"] = preview["Authors"]
            if not doc['abstract']:
                if preview['abstract']:
                    doc['abstract'] = preview['abstract']
        

        #Вырезаем всё до строки с E-mail включительно:
        matchObj = re.search(r'E-mail\:.+@{1}.+\n', articleText, flags=re.IGNORECASE)
        if matchObj:
            doc['text'] = articleText[matchObj.span()[1]:]
        else:
            doc['text'] = articleText
        # print(doc['text'])

        #Вырезаем Аннотацию и всё до неё:
        if doc['abstract']:
            # Удаляем троеточие в конце
            abstractText = re.sub('...$', '', doc['abstract'])

            # doc['text'] = re.sub(abstractText, '', doc['text'])   # просто замена
            
            matchObj = re.search(re.escape(abstractText) + r'.*\n', doc['text'], flags=re.IGNORECASE)
                # re.escape(text) - экранирует в text все символы, к-рые являются Служебными для regexp
            if matchObj:
                doc['text'] = doc['text'][matchObj.span()[1]:]

    return doc


def cylen_Category_Page(url, page='all', max_posts=-1):

    if page != 'all' and page > 1:
        url += '/' + str(int(page))

    # загрузка страницы
    print('.. requesting category page ',url,' ...', end='\t \n', flush=True)

    HTML_Page = get_HTML_Page(url)

    if not HTML_Page:
        print('  ... NO HTML page found!')
        return[]

    article_ids = []

    # парсинг страницы на указатели статей (это сделано в parse_Category_Page() )  :
    article_ids += parse_Category_Page(HTML_Page, page)

    # если нет лимита или посты ещё нужны
    if max_posts <= 0 or len(article_ids) < max_posts:

    # парсинг страницы Категории по номера страниц (если страница в теме не одна)
        if page == 'all' or page == 1:
            soup = BeautifulSoup(HTML_Page, "html.parser")   #, 'html5lib'  ('html5lib' - это отдельно устанавливаемая библиотека)
            pagesTag = soup.find("ul", {'class':"paginator"})
            last_page_btn = pagesTag.find("a", {'class':"icon"})
            if last_page_btn:
                last_page_href = last_page_btn.get("href")
                # print(last_page_href)
                match = re.search(r'/(\d+)$', last_page_href)
                if match:
                    last_page_n = int(match.group(1))
                    print('Total category pages can be processed = ', last_page_n)

                    # перебрать остальные страницы категории ...
                    for i in range(2, last_page_n + 1):
                        # получить статьи с i-ой страницы категории
                        article_ids += cylen_Category_Page(url, page=i, max_posts=max_posts)

                        # проверить лимит на число собранных статей
                        if max_posts > 0 and len(article_ids) >= max_posts:
                            break

    # проверить лимит на число собранных постов
    if max_posts > 0 and len(article_ids) > max_posts:
        article_ids = article_ids[:max_posts]  # отсечь лишние

    return article_ids


def parse_Category_Page(HTML_Text, page):
    soup = BeautifulSoup(HTML_Text, "html.parser")   #, 'html5lib'  ('html5lib' - это отдельно устанавливаемая библиотека)

    article_ids = []        # список статей страницы Категории

    doc_body = soup.find("div", {"class": "main"})
    if not doc_body:
        print('Category Page error: document is invalid.')
        return []

    #Название категории статей
    topicTag = doc_body.find("h1")
    if topicTag:
        tag = topicTag.find("span")
        if tag.text == 'список научных статей':
            tag.extract()   #удаляем подтег, для вырезания его Текста

    #Проходим по всем ссылкам на статьи
    tag = doc_body.find("ul", {"class": "list"})
    if tag:
        article_li = tag.findAll("li")

        if article_li:

            print('  Articles preview on page', 1 if page=='all' else page, ':', end='\t')
            for article_preview in article_li:
                doc = {}  # словарь с данными preview статьи. Создаем - заново в каждой итерации!
                doc["topic"] = topicTag.text

                a_tag = article_preview.find("a")
                doc["url"] = a_tag.get("href")

                tag = a_tag.find("div", {"class": "title"})
                doc["title"] = tag.text

                tag = a_tag.find("p")
                doc['abstract'] = tag.text

                tag = a_tag.find("span")
                match = re.search(r'(\d+)\s*/\s*(.+)', tag.text)
                if match:
                    doc['year'] = int(match.group(1))
                    doc['Authors'] = match.group(2).split(',')

                article_ids.append(doc)

                # print(doc["topic"])
                # print(doc["url"])
                # print(doc["title"])
                # print(doc["abstract"])
                # print(doc["year"])
                # print(doc["Authors"])

            print('  Previews in page:', len(article_ids))

    return article_ids


def cylen_search(query, page='all', max_posts=-1):
    """ Download (and save as pickle) a Cylen search pages """
    """returns dict {
        status [str]: 'ok' or error,
        query [str]: origin query,
        posts [list of str]: post IDs
    }"""
    # выгрузка страницы поиска

    payload = {'q': query, 'target_type': 'posts', 'order_by': 'relevance', 'flow':''}
    url = 'https://cylen.com/ru/search'
    if page != 'all' and page > 1:
        url += '/page' + str(int(page))

    print('.. Requesting search page for `'+query+'` ...', end='\t', flush=True)

    HTML_Page = get_HTML_Page(url, query)

    # try:

        # r = requests.get(url, params=payload, headers=HEADERS, timeout=TIMEOUT)

    # except requests.ConnectionError as e:
        # print("OOPS!! Connection Error. Make sure you are connected to Internet. Technical Details given below.\n")
        # print(str(e))
        # return
    # except requests.Timeout as e:
        # print("OOPS!! HTTP Timeout Error:")
        # print(str(e))
    # except requests.RequestException as e:
        # print("OOPS!! General HTTP Error:")
        # print(str(e))
        # return
    # except KeyboardInterrupt as e:
        # if really_exit_by_Ctrl_C():
            # return []
        # else:
            # print("Restarting interrupted search ...", flush=True)
            # return cylen_search(query, page, max_posts) # recurse with same args
    # finally:
        # print("Finished TRY block")


    # print('\nresponse:')
    # print(r.ok)
    # print(r.url)
    # print(r.links)

    # if r.status_code != 200:
        # print('search error: status_code =', status_code)
        # return []
    if not HTML_Page:
        return []

    # print('  > got it!', flush=True)

    # парсинг документа
    soup = BeautifulSoup(HTML_Page, "html.parser")   #, 'html5lib'  ('html5lib' - это отдельно устанавливаемая библиотека)

    search_doc = {}  # словарь с результатами поиска
    post_ids = []
    doc_ok = True  # статус документа (False, ничего не найдено)

    doc_body = soup.find("div", {"class": "page__body"})
    if not doc_body:
        print('search error: document is invalid.')
        return []
    confused_h2 = doc_body.find("h2", {"class": "search-results-title"})
    if confused_h2 or len(doc_body.contents) < 3:
        print('search error: cylen is confused.')
        # search_doc['status'] = 'nothing_found'
        doc_ok = False
        # return []

    if not soup.find("article", {"class": "post_preview"}):
        # нет ответов по запросу (! проверить !)
        # search_doc['status'] = 'nothing_found'
        print('search error: it seems like nothing found.')
        doc_ok = False
    else:
        # search_doc['status'] = 'ok'
        # Ищем все preview постов          content-list__item_post
        posts_li = doc_body.findAll("li", {"class": "content-list__item_post"})
        if posts_li:
            print('got.', flush=True)
            print('  Post IDs on page', 1 if page=='all' else page, ':', end='\t')
            for post_preview in posts_li:
                post_id_str = post_preview.get('id')  # ex. `post_201874`
                post_id = int(post_id_str.split('_')[1])
                # print(post_id, end='\t')
                post_ids.append(post_id)

            # print('Total:', len(post_ids))
            print(len(post_ids), 'total')

    # print('doc_ok:', doc_ok)
    # with open('deb.txt', encoding='utf-8', mode='w') as f:
        # print('r.text:\n', r.text, file=f)

    # если обрабатывается главная страница
    if doc_ok and page == 'all':
        # если нет лимита или посты ещё нужны
        if max_posts <= 0 or len(post_ids) < max_posts:
            # цикл по всем страницам
            # находим кол-во доступных страниц
            # toggle-menu__item-link toggle-menu__item-link_pagination toggle-menu__item-link_bordered
            # last_page_btn = doc_body.find("a", {"title": "Последняя страница", "class": "toggle-menu__item-link_pagination"})
            last_page_btn = soup.find("a", {"title": "Последняя страница"})
            if last_page_btn:
                last_page_href = last_page_btn.get("href")
                match = re.search(r'/ru/search/page(\d+)/', last_page_href)
                if match:
                    last_page_n = int(match.group(1))
                    print('Total search pages can be processed:', last_page_n)

                    # перебрать страницы поиска ...
                    for i in range(2, last_page_n + 1):
                        # получить посты с i-ой страницы поиска
                        post_ids += cylen_search(query, page=i, max_posts=max_posts)

                        # проверить лимит на число собранных постов
                        if max_posts > 0 and len(post_ids) >= max_posts:
                            break

        # Собрать доп. данные по результатам поиска
        menu_div = soup.find("div", {"class": "tabs-menu"})
        if menu_div:
            search_doc["info"] = menu_div.text
            search_doc["info"] = re.sub(r'\s*^[ \t]*(?=\d)', ': ', search_doc["info"], re.M)  ### ??
            search_doc["info"] = re.sub(r'\s{2,}', '\t', search_doc["info"])
            search_doc["info"] = search_doc["info"].strip()

        # проверить лимит на число собранных постов
        if max_posts > 0 and len(post_ids) > max_posts:
            post_ids = post_ids[:max_posts]  # отсечь лишние

        # сохранить результаты в файл
        search_doc['query'] = query
        search_doc["posts"] = post_ids
        search_doc["limit"] = max_posts
        fname = os.path.join(SEARCH_DIR, 'q=' + str(query) + '.txt')
        fname = fit_filename(fname)

        # сохранить дамп объекта
        fname_pkl = re.sub(r'\.txt$', '.pkl', fname)
        with open(fname_pkl, 'wb') as f:
            pickle.dump(search_doc, f)

        search_doc["count"] = len(post_ids)

        # сохранить в текстовом виде
        with open(fname, mode='w', encoding='utf-8') as f:
            for k in search_doc:
                print('%s:\t'%k,search_doc[k], file=f)
            print('\n# in python format:', file=f)
            print(search_doc, file=f)
            print("File with search results saved:")
            print(" ",fname)



    return post_ids


#    Преобразование "длинного" имени-идентификатора статьи в короткий кусок 16-ричный цифр
def str2hexid(string, len_limit=HASH_ID_LEN):
    d = hashlib.md5(string.encode()).hexdigest()
    return str(d[:len_limit])


if __name__ == '__main__':

    args = parse_cmdline()
    if not args.url:
        print('  Incorrect URL. It must begin by "' + DOMEN+'"')
        exit()

    prepare_dir(ARTICLES_DIR)
    prepare_dir(TOPIC_DIR)
    prepare_dir(SEARCH_DIR)


    print('Starting...', flush=True)

#     id_list = cylen_search(args.query, max_posts=args.limit)
#     # print('returned:', id_list)
#     print('TOTAL posts found:', len(id_list))

#     print()
#     print('Downloading posts...', flush=True)
#     for article_id in id_list:
#         save_cylen_article(post_id)

#     mys = 'Загрузка статей из файлов обратно в память'
# #     mys = 'parse_screencast_page(html_doc, args.destination, args.translit_names)'
#     print(mys)
#     print(str2hexid(mys))

    if args.type == 'a':
        save_cylen_article(args.url)

        # hrid = 'vliyanie-sotsialnyh-praktik-na-diskursivnoe-prostranstvo-fotografii'
        # save_cylen_article('/article/n/' + hrid)
    elif args.type == 'c':
        id_list = cylen_Category_Page(args.url, max_posts=args.limit)
        i=1
        for k in id_list:
            k["number"] = i
            i+=1

        # сохранить результаты preview в файл
        fname = os.path.join(TOPIC_DIR, id_list[0]['topic'] + '.txt')
        fname = fit_filename(fname)

        # сохранить дамп списка preview статей
        fname_pkl = re.sub(r'\.txt$', '.pkl', fname)
        with open(fname_pkl, 'wb') as f:
            pickle.dump(id_list, f)

        # сохранить в текстовом виде
        with open(fname, mode='w', encoding='utf-8') as f:
            for k in id_list:
                # print("  item number:", k["number"])
                articleID = k["url"].split('/')
                articleID = str2hexid(articleID[len(articleID)-1]) + '.pkl'
                print('%s:\t%s\t%s' % (k["number"], articleID, k["title"]) , file=f)
        print("File with category previews saved:")
        print(" ",fname + ' (.pkl)\n')

        # Проход по страницам со статьями
        for article_id in id_list:
            save_cylen_article(DOMEN + article_id["url"], preview=article_id)

    else:
        pass
        # id_list = cylen_search(args.query, max_posts=args.limit)
        # print('returned:', id_list)
        # print('TOTAL posts found:', len(id_list))
        # for article_id in id_list:
            # save_cylen_article(post_id)

    print('\nDone!\n')

# Загрузка статей из файлов обратно в память:
# with open('200394.pkl', mode='rb') as f:
#    doc = pickle.load(f)
