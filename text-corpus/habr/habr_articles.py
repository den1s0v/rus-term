""" Habr posts Downloader
Date:       15.04.2019

Usage examples:
===============
1. Save up to 40 posts that has a tag `ООП`:

py habr_articles.py -q "[ООП]" --limit 40

2. Save all posts that relevant to `ООП`:

py habr_articles.py -q "ООП"


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
import os
import pickle
import re
from time import sleep
# import shutil
# import ssl
# from urllib.request import Request, urlopen
# import urllib.parse

from bs4 import BeautifulSoup
import requests
# import transliterate

# limit for names (with ext.) of files to be saved
MAX_FILENAME_LENGTH = 60
CTRL_C_TIMEOUT = 3 # seconds to think before execution continues

POSTS_DIR = 'posts/'
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
        description='Download all graphic files (.png, .jpeg, .jpg) from a webpage.'
    )
    parser.add_argument("--query", "-q", 
                        help="What to search on Habr", 
                        required=True)
    parser.add_argument("--limit", "-l", 
                        default='0', 
                        help="Save only first L posts from search results sorted by relevance, ignore others (default: no limit)", 
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

    if args.query:
        args.query = args.query.strip()
        args.limit = int(args.limit)
        # report parameters
        print('Habr posts Downloader is started with parameters:')
        print('Search query:      ', '`'+args.query+'`')
        print('max posts to save: ',args.limit)
        # print('Log file:       ',args.log_file)
        # print('Translit names: ',args.translit_names)
        print()
    
    return args


def fit_filename(path):
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
        
    # rename if exists
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



def save_habr_post_by_id(pid, overwrite=False):
    """ Download (and save as pickle) a Habr document metadata (title, tags, hubs) """
    
    if not overwrite:
        # check if file already exists (i.e. full post has been saved before)
        fname = os.path.join(POSTS_DIR, str(pid) + '.pkl')
        if os.path.exists(fname):
            print('* post is already saved, skipping:',pid, flush=True)
            return # avoid to download duplicates
    
    # выгрузка документа
    print('* requesting post',pid,'...', end='\t', flush=True)
    
    try:
    	
        # r = requests.get('https://habrahabr.ru/post/' +str(pid) + '/')
        r = requests.get('https://habr.com/ru/post/' +str(pid) + '/', headers=HEADERS, timeout=TIMEOUT)

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
            print("Restarting interrupted saving of post",pid,"...", flush=True)
            return save_habr_post_by_id(pid) # recurse with same args

            
    # парсинг документа
    while True:  # (пока не получится или пока не прервут)
        try:
            
            soup = BeautifulSoup(r.text, 'html5lib') # instead of html.parser ## run 'pip install html5lib' first!
            # soup = BeautifulSoup(r.text)
            
            doc = {}  # словарь с данными поста (статьи)
            doc_ok = True  # статус документа (False, если статья удалена)
            doc['id'] = pid
            if not soup.find("span", {"class": "post__title-text"}):
                # такое бывает, если статья не существовала или удалена
                doc['status'] = 'title_not_found'
                doc_ok = False
            else:
                doc['status'] = 'ok'
                doc['title'] = soup.find("span", {"class": "post__title-text"}).text
                doc['time'] = soup.find("span", {"class": "post__time"}).text
                
                type_span = soup.find("span", {"class": "post__type-label"})
                doc['type'] = type_span.text  if type_span else  'Unspecified'
                
                # create other fields: hubs, tags, views, comments, votes, etc.
                # ...
                # doc['hubs'] = [li.text for li in soup.findAll("li", {"class": "inline-list__item_hub"})] #  ! - захватывает лишние знаки вокруг слов
                doc['hubs'] = [li.text for li in soup.findAll("a", {"class": "inline-list__item-link hub-link"})]
                doc['tags'] = [li.text for li in soup.findAll("li", {"class": "inline-list__item_tag"})]
                
                # поместить самый большой кусок данных - текст статьи - в конце.
                doc['text'] = soup.find("div", {"class": "post__text"}).text
        
            break  # успех! finish while(True).

        except KeyboardInterrupt:
            if really_exit_by_Ctrl_C():
                return  # прервали
            else:
                print("Restarting parsing of HTML page ...", flush=True)
                return save_habr_post_by_id(pid) # recurse with same args
    
    
    # сохранение результата в отдельный файл
    fail_prefix = '' if doc_ok else '-'
    fname = os.path.join(POSTS_DIR, fail_prefix + str(pid) + '.pkl')
    with open(fname, 'wb') as f:
        pickle.dump(doc, f)        

    # завершить строку с '...' кратким отчётом
    if doc_ok:
        print(len(r.text) // 1024, 'Kb of html', '('+str(len(doc['text']) // 1024), 'Kb of content) OK')
    else:
        print('NO article found!')
    
        
def habr_search(query, page='all', max_posts=-1):
    """ Download (and save as pickle) a Habr search pages """
    """returns dict {
        status [str]: 'ok' or error,
        query [str]: origin query,
        posts [list of str]: post IDs
    }"""
    # Поиск `[ООП]` (наверно, это нотация тегов)
    # https://habr.com/ru/search/?target_type=posts&order_by=relevance&q=%5BООП%5D&flow=
    # Поиск `#ООП` выдаёт то же, что и просто `ООП` (но не то, что выше)
    
    # выгрузка страницы поиска
    
    payload = {'q': query, 'target_type': 'posts', 'order_by': 'relevance', 'flow':''}
    url = 'https://habr.com/ru/search'
    if page != 'all' and page > 1:
        url += '/page' + str(int(page))
        
    print('* Requesting search page for `'+query+'` ...', end='\t', flush=True)
    
    try:
    
        r = requests.get(url, params=payload, headers=HEADERS, timeout=TIMEOUT)
        
    except requests.ConnectionError as e:
        print("OOPS!! Connection Error. Make sure you are connected to Internet. Technical Details given below.\n")
        print(str(e))
        return
    except requests.Timeout as e:
        print("OOPS!! HTTP Timeout Error:")
        print(str(e))
    except requests.RequestException as e:
        print("OOPS!! General HTTP Error:")
        print(str(e))
        return
    except KeyboardInterrupt as e:
        if really_exit_by_Ctrl_C():
            return []
        else:
            print("Restarting interrupted search ...", flush=True)
            return habr_search(query, page, max_posts) # recurse with same args
    # finally:
        # print("Finished TRY block")
            

    # print('\nresponse:')
    # print(r.ok)
    # print(r.url)
    # print(r.links)

    if r.status_code != 200:
        print('search error: status_code =', status_code)
        return []
    
    # print('  > got it!', flush=True)

    # парсинг документа
    soup = BeautifulSoup(r.text, 'html5lib')
    
    search_doc = {}  # словарь с результатами поиска
    post_ids = []
    doc_ok = True  # статус документа (False, ничего не найдено)
    
    doc_body = soup.find("div", {"class": "page__body"})
    if not doc_body:
        print('search error: document is invalid.')
        return []
    confused_h2 = doc_body.find("h2", {"class": "search-results-title"})
    if confused_h2 or len(doc_body.contents) < 3:
        print('search error: habr is confused.')
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
                        post_ids += habr_search(query, page=i, max_posts=max_posts)
                        
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
    
   
if __name__ == '__main__':
            
    args = parse_cmdline()
    
    prepare_dir(POSTS_DIR)   
    prepare_dir(SEARCH_DIR)   
    
    ### OLD Code
    # if 'http' in args.url:
        # print("fetching main webpage...")
        # html_doc = fetch_url(args.url)
    # else:
        # fnm = 'screencast.htm'
        # with open(fnm, 'r', errors='ignore') as f:
            # html_doc = f.read()
    
    # try:
        # # Do the work!
        # parse_screencast_page(html_doc, args.destination, args.translit_names)
        # print('Done!')
    # except Exception as e:
        # print('Interrupted:',str(e))
        
    print('Starting...', flush=True)

    # habr_post_id = 346198
    # habr_post_id = 200394
    # habr_post_id = 201874
    # save_habr_post_by_id(habr_post_id)
    # for post_id in range(habr_post_id, habr_post_id + 10):
        # save_habr_post_by_id(post_id)
    
    id_list = habr_search(args.query, max_posts=args.limit)
    # print('returned:', id_list)
    print('TOTAL posts found:', len(id_list))

    print()
    print('Downloading posts...', flush=True)
    for post_id in id_list:
        save_habr_post_by_id(post_id)
        
    print('Done!')
    
# Загрузка статей из файлов обратно в память:
# with open('200394.pkl', mode='rb') as f:
#	 doc = pickle.load(f)
    