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
import time
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
HTTP_TIMEOUT = 15 # seconds

LITERATURE = [r'СПИСОК\s{,5}ЛИТЕРАТУРЫ', 'Литература', r'Библиографический\s{,5}список', 'Библиография',
    r'список\s{,5}использованных\s{,5}источников', r'список\s{,5}использованной\s{,5}литературы', 'References']
KEYWORDS_TITLE = r'Ключевые\s+слова|Список\s+ключевых\s+слов'
ARTICLES_IN_PREVIEW = 20    # В Киберленинке их именно 20 штук на каждой полной странице
ARTICLES_TO_SLEEP = 1
QuietLog = False
LOAD_TIMEOUT = 1
MARGIN_FACTOR = [0.1, 0.2]      #коэффициенты расположения объекта в тексте относительно [начала, конца]  текста

pages_Requested = 0
startArticle_Number = 1
ArticleSaving_Number = 1
articleSkipped = False
Previews_Topic = ''
SavedPreviews = []
notLoadedLists = ([], [])
skipped = 0
no_HTML_pages = 0

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
        url               (for -u option)
        type              (for -t option)
        query             (for -q option)
        limit             (for -l option)
        OverwriteArticles (for -w option)
        toSleep           (for -s option)
        Timeout           (for -to option)
        QuietLog          (for -ql option)

    """
    parser = argparse.ArgumentParser(
        description='Download articles from "Cyberleninka.ru"'
    )
    parser.add_argument("--url", "-u",
                        help="webpage source full URL",
                        required=True)
    parser.add_argument("--type", "-t",
                        help="URL type: a - article page, c - category page, s - search page",
                        choices=['a','c','s'],
                        required=True)
    # parser.add_argument("--query", "-q",
                        # help="What to search and then download",
                        # required=False)
    parser.add_argument("--limit", "-l",
                        default='0',
                        help="Save only first L articles from search results sorted by relevance, ignore others (default: no limit)",
                        required=False)
    parser.add_argument("--OverwriteArticles", "-w", 
                        dest='Overwrite',
                        action="store_true", 	#если опция Присутствует, то понимать её как True, иначе False
                        help="If present then overwrite existing article files", 
                        required=False)
    parser.add_argument("--toSleep", "-s",
                        default='1',
                        help="Articles quantity to sleep while saving articles (default: 1)",
                        required=False)
    parser.add_argument("--Timeout", "-to",
                        default='1',
                        help="Sleep timeout (default: 1 second)",
                        required=False)
    parser.add_argument("--QuietLog", "-ql", 
                        dest='Quiet',
                        action="store_true", 	#если опция Присутствует, то понимать её как True, иначе False
                        help="If present then quiet log", 
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
        # if args.query:
            # args.query = args.query.strip()
        args.limit = int(args.limit)
        args.toSleep = int(args.toSleep)
        args.Timeout = int(args.Timeout)
        args.Overwrite = bool(args.Overwrite)
        args.Quiet = bool(args.Quiet)
        # report parameters
        if args.type == 'a':
            mode = 'article'
        elif args.type == 'c':
            mode = 'category'
        else:
            mode = 'search'
        print('"Cyberleninka" articles Downloader started with parameters:')
        print(' URL type:            ', '`'+mode+'`'+' page')
        # if args.query:
            # print(' Search query:        ', '`'+args.query+'`')
        print(' max articles to save:',args.limit, ('(no limit)' if args.limit <= 0 else '') )
        print(' Articles quantity to sleep:',args.toSleep)
        print(' Sleep timeout:       ',args.Timeout)
        print(' Overwrite existing article files:', ('Yes' if args.Overwrite else 'No') )
        print(' Using URL:           ',args.url)
        print(' Quiet log:', ('Yes' if args.Quiet else 'No') )
        # print(' Log file:       ',args.log_file)
        # print(' Translit names: ',args.translit_names)
        print()
        
        # print('Вывести зарегистрированные ключевые слова ArgumentParser:')
        # print(parser._registries) # это - стандартная возможность
        # print()
        # exit()
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

        r = requests.get(url, params=payload, headers=HEADERS, timeout=HTTP_TIMEOUT)

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

def getLastPathPart(url, fullURL=False):
    """ Get last part from URL path
    """
    path = url
    if fullURL:
        path = urllib.parse.urlsplit(url).path
    path = path.split('/')
    path.reverse()    
    return path[0]

# hrid : human readable ID
def save_cylen_article(url, overwrite=False, preview=None):
    """ Download (and save as pickle) a Cylen article with metadata (title, keywords, category, ...) """

    global pages_Requested, ArticleSaving_Number, articleSkipped, skipped, no_HTML_pages
    
    articleSkipped = False
    if not overwrite:
        if preview:  #Если грузим страницы статей со Списка
            if not isArticleNotLoaded(ArticleSaving_Number):
                if not QuietLog:
                    print(' %d:\tArticle saved before, skipping' % ArticleSaving_Number, flush=True)
                articleSkipped = True
                skipped += 1
                return

    hrid = getLastPathPart(url, True)

    if not overwrite:
        # check if file already exists (i.e. full post has been saved before)
        # fname = os.path.join(ARTICLES_DIR, hrid + '.pkl')
        fname = os.path.join(ARTICLES_DIR, str2hexid(hrid) + '.pkl')
        if os.path.exists(fname):
            if not QuietLog:
                print('* Article is already saved, skipping:',fname, flush=True)
            articleSkipped = True
            return # avoid to download duplicates

    # выгрузка документа
    print(' ', ArticleSaving_Number,': requesting article page "',hrid,'"...', sep='', end='\t \n', flush=True)
    # print('   full URL: ',url, flush=True)

    # HTML_Page = get_HTML_Page('https://cyberleninka.ru/article/n/' +hrid) #для отладки
    HTML_Page = get_HTML_Page(url)

    if not HTML_Page:
        print('  ... NO HTML page found!')
        no_HTML_pages += 1
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
        # ArticleSaving_Number += 1
        pages_Requested += 1
    else:
        print('NO article found!')
        with open('Err_Page.htm', 'w') as f:
            f.write(HTML_Page)
        print('Error Page saved to "Err_Page.htm"\n Exiting.')
        exit()

    return


def analyseLiterature(soup, doc_title):
    """ Считает кол-во Списков Литературы в статье,
        анализирует их расположение относительно Заголовка статьи (выше или ниже).
        Выдаёт общее кол-во Списков литературы и Номера их в массиве тегов <p>.
    """
    article = soup.find("div", {"class": "ocr", "itemprop": "articleBody"})
    literatList = [0, 0]
    ind = 0
    count = 0
    if article:
        i = 0
        for p_tag in article.findAll("p"):
            matchObj = re.match(re_Literature, p_tag.text) #ищем (с Начала тега) варианты подзаголовка типа "Список литературы"
            if matchObj:
                literatList[ind] = i
                count += 1

            matchObj = re.search(re.escape(doc_title), p_tag.text, flags=re.IGNORECASE)
            if matchObj:
                if not ind :    # если ind == 0
                    ind += 1
            i += 1
    return (count, literatList)

def analyseCoordinate(matchObj, len_Text):
    """ Анализ расположения найденного обхекта в тексте.
        Выход:
        Если конец объекта расположен ближе к началу текста, т.е. меньше в MARGIN_FACTOR раз от всей длины, то 0
        Если начало объекта находится ближе к концу текста, то 2
        Если объект находится в середине текста, то 1
    """
    if matchObj.span()[1] / len_Text <= MARGIN_FACTOR[0]:
        return 0
    elif (len_Text - matchObj.span()[0]) / len_Text <= MARGIN_FACTOR[1]:
        return 2
    return 1

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
        doc['number'] = 0
        doc['title'] = beginTag.find("span").text   # ищем внутри ТЕГА beginTag
        doc['title'] = re.search('«(.+)»', doc['title']).group(1)

        #Ищем Topic:
        for Tag1 in soup.findAll("div", {"class": "title"}):
            if Tag1.text == "Область наук":
                Tag2 = Tag1.findNextSibling('ul')
                Tag3 = Tag2.find("a")
                doc['topic'] = Tag3.text.strip()
                # print("doc['topic'] = ", doc['topic'])
                break
        
        #Ищем Year:
        Tag1 = soup.find("div", {"class": "label year"})
        Tag2 = Tag1.find("time", {"itemprop": "datePublished"})
        doc["year"] = Tag2.text
        # print("doc['year'] = ", doc['year'])
        
        #Ищем Authors:
        doc["Authors"] = []
        Tag1 = soup.find("ul", {"class": "author-list"})
        for Tag2 in Tag1.findAll("li", {"itemprop": "author"}):
            # Author = Tag2.find("span").text   # здесь кроме <span> встречается еще и <a>
            Author = Tag2.text
            doc["Authors"].append(Author.strip())       
        # print("doc['Authors'] = ", doc['Authors'])
        
        #Пишем URL (если режим ОДНОЙ статьи):
        if args.type == 'a':
            doc['url'] = urllib.parse.urlsplit(args.url).path
            # print("doc['url'] = ", doc['url'])
        else:
            doc['url'] = ""
        
        
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

        #Проверяем Аннотацию на отсутствие русских букв:
        if doc['abstract']:
            matchObj = re.match('[а-яё]', doc['abstract'], flags=re.IGNORECASE)
            if not matchObj:
                doc['abstract'] = ''  #русских букв не найдено, - обнуляем

        article = soup.find("div", {"class": "ocr", "itemprop": "articleBody"})
        
        #Список литературы
        matchObj = re.search(r'СПИСОК ЛИТЕРАТУРЫ([\s\S]+)' + re.escape(doc['title']), article.text, flags=re.IGNORECASE)
        if matchObj:
            bibList = matchObj.group(1) #сейчас не используется
        # print(bibList)

        #Вырезаем все Списки литературы (обычно их 2 шт., - в начале и в конце)  <<<< new variant
        #используем здесь метод  тега .findNextSibling() чтобы перейти к Следующему тегу (этого же уровня) от Данного.
        # свойство nextTag = tag.nextSibling - перейдет сначала не на следующий тег, в на следующую NavigableString
        
        literatData = analyseLiterature(soup, doc['title'])

        if literatData[1][0]:
            for p_tag in article.findAll("p"):
                matchObj = re.match(re_Literature, p_tag.text) #ищем (с Начала тега) варианты подзаголовка типа "Список литературы"
                if matchObj:
                    lit_tag = p_tag
                    # print('lit_tag=', lit_tag)
                    lit_item = lit_tag.findNextSibling('p')  # перейти на следующий тег <p>
                    
                    lit_tag.extract()
                    while (lit_item and re.search(r'^(\s*\d+\.\s+)+', lit_item.text) ):
                        # print('lit_item=', lit_item.text[:60])
                        _lit_item = lit_item
                        lit_item = lit_item.findNextSibling('p')
                        _lit_item.extract()
                        
                    break   #второй (нижний) СписокЛитературы будем убирать из текста


        #Вырезаем все рекламные вставки
        allDivs = article.findAll("div")
        for t in allDivs:
            t.extract()

        #Формируем Общий Текст:
        
        articleText = ""
        for t in article.findAll("p"):
            t_Content = t.text

            # if (re.search(r'^(\s*\d+\.\s+)+', t_Content.lstrip()) != None or  #пункты Списка литературы
                # re.search(LITERATURE[0], t_Content, flags=re.IGNORECASE) or   # подзаголовки "Список литературы"
                # re.search(LITERATURE[1], t_Content, flags=re.IGNORECASE) or
                # re.search(re.escape(doc['title']), t_Content, flags=re.IGNORECASE) ):   # Заголовок статьи
                # t.extract()
            # else:
            if len(t_Content) > 1 and t_Content[-1] == '-':
                articleText += t_Content[:-1]   #соединяем Переносы
            else:
                articleText += t_Content + '\n'
                
        doc['text'] = articleText
        articleText = None

        if preview:  #Переносим данные из Словаря preview
            doc['number'] = preview['number']
            if preview['topic']:
                doc['topic'] = preview['topic']
            if not doc['url']:
                doc['url'] = preview['url']
            if not doc['year']:
                if preview["year"]:
                    doc["year"] = preview["year"]
            if not doc['Authors']:
                if preview["Authors"]:
                    doc["Authors"] = preview["Authors"]
            if not doc['abstract']:
                if preview['abstract']:
                    doc['abstract'] = preview['abstract']
            if not doc['title']:
                if preview['title']:
                    doc['title'] = preview['title']
        

        #Вырезаем  Заголовок статьи и всё до него:
        matchObj = re.search(re.escape(doc['title']), doc['text'], flags=re.IGNORECASE)
        if matchObj:
            doc['text'] = doc['text'][matchObj.span()[1]:]

        #Вырезаем часть текста, работая со строкой с E-mail (вырезаем включительно E-mail):
        # Нижние
        while(True):
            # matchObj = re.search(r'E-mail\s*\:\s*\w+@\w+\..+\n[^@]*$', doc['text'], flags=re.IGNORECASE)
            matchObj = re.search(r'E-mail\s*\:\s*\w+@\w+\..+\n(?=[^@]*$)', doc['text'], flags=re.IGNORECASE) # - второй вариант
                # регулярки - для экономии памяти
            if not matchObj:
                break
            else:
                coordinate = analyseCoordinate(matchObj, len(doc['text']))
                if coordinate != 2:
                    break
                doc['text'] = doc['text'][:matchObj.span()[0]]
                    
        while(True):
        # Остальные
            matchObj = re.search(r'E-mail\:\s*\w+@\w+\..+\n', doc['text'], flags=re.IGNORECASE)
            if not matchObj:
                break
            else:
                coordinate = analyseCoordinate(matchObj, len(doc['text']))
                if coordinate == 0:   # E-mail находится вначале текста
                    doc['text'] = doc['text'][matchObj.span()[1]:]
                elif coordinate == 2:   # E-mail находится конце текста
                    doc['text'] = doc['text'][:matchObj.span()[0]]
                else:   # coordinate == 1:   # E-mail находится в середине текста
                    doc['text'] = doc['text'][:matchObj.span()[0]] + doc['text'][matchObj.span()[1]:]

        # else:   # E-mail не была найдена
            # pass
        # print(doc['text'])
        

        #Дополняем Аннотацию до конца, если она была указана не полностью:
        if doc['abstract']:
            # Удаляем троеточие в конце
            matchObj = re.search('...$', doc['abstract'])
            if matchObj:
                abstractText = re.sub('...$', '', doc['abstract'])
                # print("doc['abstract'] ДО = ", doc['abstract'][-25:])
                
                matchObj = re.search('('+re.escape(abstractText) + r'.*)\n', doc['text'], flags=re.IGNORECASE)
                    # re.escape(text) - Экранирует в text все символы, к-рые являются Служебными для regexp
                if matchObj:
                    doc['abstract'] = matchObj.group(1)
                    # print("doc['abstract'] ПОСЛЕ = ", doc['abstract'][-25:])

        else:   # Тогда ищем Аннотацию в самом тексте
            matchObj = re.search(r'\n\s*Аннотация\.?\s*(.+)\n', doc['text'], flags=re.IGNORECASE)
            if matchObj:
                doc['abstract'] = matchObj.group(1).strip()

                
        #Вырезаем Аннотацию и всё до неё:
        if doc['abstract']:
            # doc['text'] = re.sub(abstractText, '', doc['text'])   # просто замена
            
            matchObj = re.search(re.escape(doc['abstract']) + r'\n', doc['text'], flags=re.IGNORECASE)
                # re.escape(text) - экранирует в text все символы, к-рые являются Служебными для regexp
            if matchObj:
                doc['text'] = doc['text'][matchObj.span()[1]:]


        #Ищем (и вырезаем) в тексте Ключевые слова:
        matchObj = re.search(r'^\s*(?:' +KEYWORDS_TITLE +')\s*[-.:]?\s*(.+)\n', doc['text'], flags=re.IGNORECASE|re.MULTILINE)
            # здесь re.MULTILINE  - из-за знака ^ (крышка) - чтобы поиск начинался с Начала КАКОЙ-ЛИБО строки ВНУТРИ
        if matchObj:
            if not doc['keywords']:
                # doc['keywords'] = matchObj.group(1).split(',')    # <--- возможны пробелы в элементах _keywords
                # убираем эти пробелы:
                _keywords = matchObj.group(1).split(',')           
                doc['keywords'] = list( map( lambda param: param.strip() , _keywords) )  #для удаления пробелов из элеменов list
            # Вырезаем keywords из текста:
            coordinate = analyseCoordinate(matchObj, len(doc['text']))
            if coordinate == 0:   # keywords находятся вначале текста
                doc['text'] = doc['text'][matchObj.span()[1]:]
            elif coordinate == 2:   # keywords находятся конце текста
                doc['text'] = doc['text'][:matchObj.span()[0]]
            else:    # keywords находятся в середине текста
                doc['text'] = doc['text'][:matchObj.span()[0]] + doc['text'][matchObj.span()[1]:]
            
                
        if literatData[1][1]:
            #Вырезаем второй (нижний) СписокЛитературы
            matchObj = re.search(re_Literature_text, doc['text'])
            if matchObj:
                doc['text'] = doc['text'][:matchObj.span()[0]]

        # Список похожих статей
        fullTags = soup.findAll("div", {"class": "full"})
        for t1 in fullTags:
            t2 = t1.find("h2", {"class": "right-title"})
            if t2 and "Похожие темы" in t2.text:
                t_full = t1
                break
            
        if t_full:
            doc['similar'] = []
            similarList = t_full.findAll("li")
            for similar in similarList:
                t_link = similar.find("a", {'class':"similar"})
                similar_url = t_link.get("href")                
                
                if similar_url[:11] != '/article/n/':
                    continue
            
                similarTitle = t_link.find("div", {'class':"title"}).text
                doc['similar'].append( {'similar_url' : similar_url, 'similarTitle' : similarTitle} )

    return doc


def cylen_Category_Page(url, page='all', max_posts=-1):

    global pages_Requested, startArticle_Number, ArticleSaving_Number, Previews_Topic, notLoadedLists, skipped

    currentPage = 1

    if page != 'all' and page > 1:
        url += '/' + str(int(page))
        currentPage = page
    
    startPage = 1
    if page == 'all':
        skipped = 0

        pages_Requested = 0
        startArticle_Number = 1
        matchObj = re.search(r'/(\d+)$', url)
        if matchObj:   #подан  url, в к-ром уже присутствует Номер страницы (страница - не Первая с списке)
            startPage = int(matchObj.group(1))
            next_URLs = url[:matchObj.span()[0]]
            
            startArticle_Number = (startPage - 1) * ARTICLES_IN_PREVIEW + 1
            currentPage = startPage

        ArticleSaving_Number = startArticle_Number
            
    # загрузка страницы
    print(' requesting category page "',url,'" ...', sep='', end='\t \n', flush=True)

    HTML_Page = get_HTML_Page(url)

    if not HTML_Page:
        print('  ... NO HTML page found!')
        return[]

    if page == 'all':
        Previews_Topic = get_TopicFromCategory_Page(HTML_Page)
        print('Previews_Topic:\t"' + Previews_Topic +'"')
        if Previews_Topic:
            load_SavedPreviews()
            notLoadedLists = get_ListsArticleNotSaved_Numbers()
        if not QuietLog:
            print('\n-->>  Диапазоны несохранённых ранее  preview_List:')
            print(notLoadedLists[0])
            print('-->>  Диапазоны несохранённых ранее  article_List:')
            print(notLoadedLists[1])
            print()
        
        # exit()

    article_ids = []

    # парсинг страницы на указатели статей (это сделано в parse_Category_Page() )  :
    # article_ids += parse_Category_Page(HTML_Page, page)
    Saving_Number = ArticleSaving_Number    
    
    page_ids = parse_Category_Page(HTML_Page, currentPage)    
    article_ids += page_ids
    
    skipped += ArticleSaving_Number - Saving_Number - len(page_ids)

    # если нет лимита или посты ещё нужны
    if max_posts <= 0 or len(article_ids) < max_posts     -skipped:

    # парсинг страницы Категории по номера страниц (если страница в теме не одна)
        if page == 'all' or page == 1:
            soup = BeautifulSoup(HTML_Page, "html.parser")   #, 'html5lib'  ('html5lib' - это отдельно устанавливаемая библиотека)
            pagesTag = soup.find("ul", {'class':"paginator"})
            
            li_tags = pagesTag.findAll("li")
                #если открыта Последняя страница, то здесь, внутри последнего <li> будет не <a>, а <span> :
            last_page_btn = li_tags[-1].find("a")
            
            if last_page_btn:
                last_page_href = last_page_btn.get("href")
                # print(last_page_href)
                match = re.search(r'/(\d+)$', last_page_href)
                if match:
                    last_page_n = int(match.group(1))
                    print('\nCategory pages can be processed = ', last_page_n - startPage + 1)
                    print('Total category pages = ', last_page_n, '\n')

                    # перебрать остальные страницы категории ...
                    if startPage <= 1:
                        next_URLs = url
                    
                    for i in range(startPage + 1, last_page_n + 1):
                        # получить статьи с i-ой страницы категории
                        if is_PreviewPage_NotLoaded(i):
                            article_ids += cylen_Category_Page(next_URLs, page=i, max_posts=max_posts)
                            pages_Requested += 1
                            
                            isTimeToSleep = (ARTICLES_TO_SLEEP <= 1) or (pages_Requested % ARTICLES_TO_SLEEP)
                            if pages_Requested > 0 and isTimeToSleep:
                                print("\tPausing for", LOAD_TIMEOUT, "seconds to avoid ban...", flush=True)
                                sleep(LOAD_TIMEOUT)

                        else:
                            if not QuietLog:
                                print(' %d:\tPreview page saved before, skipping' % i, flush=True)
                            
                            if max_posts <= 0 or (i * ARTICLES_IN_PREVIEW + 1)  <=  (startArticle_Number + max_posts):
                                sk = ARTICLES_IN_PREVIEW
                                ArticleSaving_Number += sk
                            else:   # пропустили ПОСЛЕДНЮЮ разрешенную страницу
                                sk = i * ARTICLES_IN_PREVIEW + 1 -  (startArticle_Number + max_posts)
                                ArticleSaving_Number += ARTICLES_IN_PREVIEW - sk
                                
                            skipped += sk
                            
                        # проверить лимит на число собранных статей
                        if max_posts > 0 and len(article_ids) >= max_posts     -skipped:
                            break

    # проверить лимит на число собранных постов
    if page == 'all':
        skipped = ArticleSaving_Number - startArticle_Number - len(article_ids)
        sk = skipped
        if skipped > max_posts:
            skipped = max_posts
        if max_posts > 0 and len(article_ids) > max_posts     -skipped:
            article_ids = article_ids[:max_posts     -skipped]  # отсечь лишние
        print('Skipped Preview items:  ', sk, ' '*8 + 'Saved Preview items:  ', len(article_ids))

    return article_ids


def get_TopicFromCategory_Page(HTML_Text):
    """Выдаёт Название категории статей
    """
    soup = BeautifulSoup(HTML_Text, "html.parser")   #, 'html5lib'  ('html5lib' - это отдельно устанавливаемая библиотека)
    doc_body = soup.find("div", {"class": "main"})

    topic = ''
    if doc_body:
        topicTag = doc_body.find("h1")
        if topicTag:
            tag = topicTag.find("span")
            if tag.text.lower() == 'список научных статей':
                topic = doc_body.h1.contents[0].strip()
    return topic

def parse_Category_Page(HTML_Text, page):

    global ArticleSaving_Number
    
    soup = BeautifulSoup(HTML_Text, "html.parser")   #, 'html5lib'  ('html5lib' - это отдельно устанавливаемая библиотека)

    article_ids = []        # список статей страницы Категории

    doc_body = soup.find("div", {"class": "main"})
    if not doc_body:
        print('Category Page error: document is invalid.')
        return []

    #Название категории статей
    # topicTag = doc_body.find("h1")
    # if topicTag:
        # tag = topicTag.find("span")
        # if tag.text.lower() == 'список научных статей':
            # tag.extract()   #удаляем подтег, для вырезания его Текста
    # topic = get_TopicFromCategory_Page(HTML_Text)

    #Проходим по всем ссылкам на статьи
    tag = doc_body.find("ul", {"class": "list"})
    if tag:
        article_li = tag.findAll("li")

        if article_li:

            print('  Articles preview on page', 1 if page=='all' else page, ':\t', len(article_li))   # , end='\t'
            for article_preview in article_li:
                if not isPreviewNotLoaded(ArticleSaving_Number):
                    if not QuietLog:
                        print(' %d:\tPreview saved before, skipping' % ArticleSaving_Number, flush=True)
                    ArticleSaving_Number += 1
                    continue

                doc = {}  # словарь с данными preview статьи. Создаем - заново в каждой итерации!
                doc['number'] = ArticleSaving_Number
                # doc["topic"] = topicTag.text.strip()
                doc["topic"] = Previews_Topic

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
                    doc['Authors'] = list( map( lambda param: param.strip() , doc['Authors']) )  # удаляем пробелы
                
                article_ids.append(doc)
                # print('ArticleSaving_Number после append \t',ArticleSaving_Number)
                ArticleSaving_Number += 1

                # print(doc["number"])
                # print(doc["topic"])
                # print(doc["url"])
                # print(doc["title"])
                # print(doc["abstract"])
                # print(doc["year"])
                # print(doc["Authors"])

    return article_ids


def get_ListsArticleNotSaved_Numbers():
    """ Анализ и выдача ДИАПАЗОНОВ Пропусков предыдущих закачек.
        Строка с Именем Топика - взята из глобальной переменной
        Выход: кортеж из двух списков (preview_List и article_List)
          preview_List - Список диапазонов несохранённых preview статей:
          article_List - Список диапазонов несохранённых article (самих статей) - анализируется только для
            тех превьюшек, к-рые уже были сохранены раньше.
        Каждый элемент списка содержит кортеж из 2 значений диапазона НЕзакаченных ранее промежутков:
        Начало_промежутка, Конец_промежутка.
    """

    preview_List = []
    article_List = []

    # topic_fname_pkl = os.path.join(TOPIC_DIR, Previews_Topic + '.pkl')
    # if not os.path.exists(topic_fname_pkl):
        # print('Не найден файл со списком статей категории  "' + topic_fname_pkl + '"')
        # print(' Будет сгенерирован новый файл')
        # return (preview_List, article_List)

    # Загрузка данных topic'a из файла в память:     <<<-- теперь это делается в load_SavedPreviews()
    # with open(topic_fname_pkl, mode='rb') as f:
       # docs = pickle.load(f)
       
    docs = SavedPreviews
    len_docs = len(docs)
    if not docs:
        return (preview_List, article_List)

    #Считаем, что файл с данными Топика ранее уже был отсортирован  
    # нумерация статей и превьюшек начинается с 1
    articleNoSave = []
    
    for i in range( len_docs):  # 1-й параметр в range - опущен
        curr_number = docs[i]['number']
        isEndDiap = False
        if i == 0:
            previous = curr_number
        elif (curr_number - previous) > 1:
            preview_List.append( (previous +1, curr_number -1) )
            isEndDiap = True
        previous = curr_number
        
        if isEndDiap:
            if articleNoSave:
                article_List.append( (articleNoSave[0], articleNoSave[-1]) )
                articleNoSave = []

        article_fname = os.path.join(ARTICLES_DIR, str2hexid(getLastPathPart(docs[i]["url"])) + '.pkl')
        if not os.path.exists(article_fname):
            articleNoSave.append(curr_number)
        else:
            if articleNoSave:
                article_List.append( (articleNoSave[0], articleNoSave[-1]) )
                articleNoSave = []

    if articleNoSave:
        article_List.append( (articleNoSave[0], articleNoSave[-1]) )
    
    #Добавляем диапазон значений ПОСЛЕ последнего загруженного пункта
    preview_List.append( (docs[-1]['number'] + 1,  None ) )
    article_List.append( (docs[-1]['number'] + 1,  None ) )

    return (preview_List, article_List)
    
    
def isPreviewNotLoaded(number):
    return isItemInDiapasons(number, notLoadedLists[0])
    
def isArticleNotLoaded(number):
    return isItemInDiapasons(number, notLoadedLists[1])
    
def isItemInDiapasons(number, DiapList):
    if not DiapList:
        return True
    for diap in DiapList:
        if not diap[1]:
            if number >= diap[0]:
                return True
        elif number >= diap[0] and number <= diap[1]:
            return True
            
    return False
    
def is_PreviewPage_NotLoaded(num):
    """ Вход - номер страницы Preview. Страницы нумеруются с 1
        Выход: эта страница еще не загружена.
    """
    startItem = (num - 1) * ARTICLES_IN_PREVIEW + 1
    endItem = startItem + ARTICLES_IN_PREVIEW
    # Учитываем заданный юзером лимит загрузок:
    LimitInside = False
    endAllow = endItem
    if args.limit > 0:
        if endItem >= startArticle_Number + args.limit:
            endAllow = startArticle_Number + args.limit - 1
            LimitInside = True
    # print('is_PreviewPage_NotLoaded(): startItem',startItem)
    # print('is_PreviewPage_NotLoaded(): endAllow',endAllow)
    
    for item in range(startItem, endItem):
        if LimitInside and item > endAllow: # это уже за гранью допустимого лимита загрузок
            # print('is_PreviewPage_NotLoaded(): выход по лимиту, item=',item)
            return False    # значит, загружать эту страницу - не надо
        if isPreviewNotLoaded(item):
            # print('is_PreviewPage_NotLoaded(): не загруженная item=',item)
            return True
            
    return False

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

        # r = requests.get(url, params=payload, headers=HEADERS, timeout=HTTP_TIMEOUT)

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


#    Преобразование "длинного" имени-идентификатора статьи в короткий кусок 16-ричных цифр
def str2hexid(string, len_limit=HASH_ID_LEN):
    d = hashlib.md5(string.encode()).hexdigest()
    return str(d[:len_limit])


def getArticlesID_toLoad():
    #Считаем, что SavedPreviews с данными Топика ранее уже БЫЛ отсортирован  
    id_list = []
    if not SavedPreviews:
        return id_list
    for i in range(len(SavedPreviews)):
        if SavedPreviews[i]["number"] == startArticle_Number:
            break
    else:
        return id_list

    if args.limit:
        id_list = SavedPreviews[i : i + args.limit]
    else:
        id_list = SavedPreviews[i : ]
    return id_list

def load_SavedPreviews():
    global SavedPreviews
    if not Previews_Topic:
        return
    fname = os.path.join(TOPIC_DIR, Previews_Topic + '.pkl')
    fname = fit_filename(fname)
    if os.path.exists(fname):
        with open(fname, mode='rb') as f:
           SavedPreviews = pickle.load(f)
    else:
        print('Не найден файл со списком статей категории  "' + fname + '"')
        print(' Будет сгенерирован новый файл')


def save_Topic_Files(fname, id_list):
    """ объединение и Сортировка старого и нового списков Previews.
        Сохранение объединенного списка в файлы .pkl и .txt
    """
    global SavedPreviews
    # сохранить дамп списка preview статей. Включая новые данные.

    fname_pkl = re.sub(r'\.txt$', '.pkl', fname)

    # if startArticle_Number > 1:   прежние данные будем анализировать ВСЕГДА (а не только если грузим НЕ сначала)    
    # Загрузка прежних данных topic'a из файла в память:     <<<-- теперь это делается в load_SavedPreviews()
    # docs = []
    pkl_exists = os.path.exists(fname_pkl)
    # if pkl_exists:
        # with open(fname_pkl, mode='rb') as f:
           # docs = pickle.load(f)
    # ## else:     # старых данных - ещё не было

    docs = SavedPreviews

    if id_list:
        docs += id_list     # пристыковываем новые данные

    if docs:
        if id_list:     # новые данные - есть
            docs.sort(key = lambda p: p["number"])      # сортируем новые данные
            SavedPreviews = docs
    
        if    not pkl_exists or id_list :    #     )and False:    #здесь убираем сохранение в файлы (для отладки)
            # Сохраняем всё в .pkl файл
            with open(fname_pkl, 'wb') as f:
                pickle.dump(docs, f)

            # сохранить в текстовом виде - файл формируем заново КАЖДЫЙ раз
            with open(fname, mode='w', encoding='utf-8') as f:
                for k in docs:
                    articleID = str2hexid(getLastPathPart(k["url"])) + '.pkl'
                    print('%s:\t%s\t%s' % (k["number"], articleID, k["title"]) , file=f)
            print("Files with category previews saved:")
            print(" ",fname + ' (.pkl)\n')

    else:
        print('No data to save to category previews files')


if __name__ == '__main__':

    args = parse_cmdline()
    if not args.url:
        print('  Incorrect URL. It must begin by "' + DOMEN+'"')
        exit()

    start_time = time.time()
    
    ARTICLES_TO_SLEEP = args.toSleep
    LOAD_TIMEOUT = args.Timeout
    QuietLog = args.Quiet
    
    prepare_dir(ARTICLES_DIR)
    prepare_dir(TOPIC_DIR)
    prepare_dir(SEARCH_DIR)
    
    #Комплируем медленную регулярку (Список для поиска вариантов подзаголовка типа "Список литературы")
    re_Literature = re.compile(r'\s*(?:'+ ('|'.join(LITERATURE)) +').{,5}$', flags=re.IGNORECASE)
    re_Literature_text = re.compile(r'\s*(?:'+ ('|'.join(LITERATURE)) + r').{,5}\n', flags=re.IGNORECASE)
    # print('  re.compile:\n', re_Literature)
    # print('  re.re_Literature_text:\n', re_Literature_text)


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
        save_cylen_article(args.url, overwrite=args.Overwrite)
        if LOAD_TIMEOUT > 0:
            print("\tPausing for", LOAD_TIMEOUT, "seconds to avoid ban...", flush=True)
            sleep(LOAD_TIMEOUT)


        # hrid = 'vliyanie-sotsialnyh-praktik-na-diskursivnoe-prostranstvo-fotografii'
        # save_cylen_article('/article/n/' + hrid)
    elif args.type == 'c':
        print('\n  >>>>  Articles preview loading ...')
        id_list = cylen_Category_Page(args.url, max_posts=args.limit)
        # i=1
        # for k in id_list:
            # k["number"] = i   #Сквозная нумерация (была раньше)
            # i+=1

        # сохранить результаты preview в файл
        if Previews_Topic:
            fname = os.path.join(TOPIC_DIR, Previews_Topic + '.txt')
            fname = fit_filename(fname)

            save_Topic_Files(fname, id_list)

        # # сохранить дамп списка preview статей        <<<<<---- сделано в save_Topic_Article()
        # fname_pkl = re.sub(r'\.txt$', '.pkl', fname)
        # with open(fname_pkl, 'wb') as f:
            # pickle.dump(id_list, f)

        # # сохранить в текстовом виде
        # with open(fname, mode='w', encoding='utf-8') as f:
            # for k in id_list:
                # print("  item number:", k["number"])
                # articleID = str2hexid(getLastPathPart(k["url"])) + '.pkl'
                # print('%s:\t%s\t%s' % (k["number"], articleID, k["title"]) , file=f)
        # print("File with category previews saved:")
        # print(" ",fname + ' (.pkl)\n')


        # Проход по страницам со статьями
        id_list = getArticlesID_toLoad()
        
        if not QuietLog:
            print('\n  Номера статей к загрузке:')
            for i, k in enumerate(id_list):
                print(k["number"], end='\t')
                if i % 10 == 9:
                    print()
            print()
        # exit()
        
        if not id_list:
            exit()      #  <<--- уже не нужно  

        print('\n  >>>>  Articles loading ...')
        # ArticleSaving_Number = startArticle_Number
        pages_Requested = 0
        skipped = 0
        no_HTML_pages = 0
        for article_id in id_list:
            ArticleSaving_Number = article_id["number"]
            save_cylen_article(DOMEN + article_id["url"], overwrite=args.Overwrite, preview=article_id)
            
            # print("pages_Requested = ",pages_Requested)
            isTimeToSleep = (ARTICLES_TO_SLEEP <= 1) or (pages_Requested % ARTICLES_TO_SLEEP)
            if not articleSkipped and pages_Requested > 0 and isTimeToSleep:
                print("\tPausing for", LOAD_TIMEOUT, "seconds to avoid ban...", flush=True)
                sleep(LOAD_TIMEOUT)
        no_HTML_str = ''
        if no_HTML_pages:
            no_HTML_str = ' '*8 + 'No HTML pages found:  ' + str(no_HTML_pages)
        print('\nSkipped Articles:  ', skipped, ' '*8 + 'Saved Articles:  ', len(id_list) -skipped -no_HTML_pages, no_HTML_str)
        print("\n   Program run time :   %s seconds ---" % round((time.time() - start_time), 2))

    else:       # если args.type == 's':
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
