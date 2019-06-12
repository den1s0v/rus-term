# coding=utf-8

import os
import pickle
import re

HABR_POSTS_DIR = 'text-corpus/habr/posts'
CYBERLENINKA_ARTICLES_DIR = 'text-corpus/cyberleninka/articles'


def load_article(pid, dir='.', quiet=False):
    """ Загружает pickle-объект из файла вида {pid}.pkl """
    fpath = '{dir}/{pid}.pkl'.format(dir=dir, pid=pid)
    no_article_path = '{dir}/-{pid}.pkl'.format(dir=dir, pid=pid)
    if not quiet:
        print('loading:',fpath)
    load_error = None
    # try to load empty article & then existing article dump
    for path in (no_article_path,fpath,):
        try:
            with open(path, mode='rb') as f:
                return pickle.load(f)
        except FileNotFoundError as e:
            load_error = e
    if load_error and not quiet:
        print(load_error)
    return None

def load_habr_corpus(limit=None, min_keywords=0):
    """
    load_habr_corpus(limit=None, min_keywords=0)
      -> list(dict('id'->str or int, 'text'->str, 'title'->str, 'keywords'->[str]))
    Keywords: объединение отфильтрованных множеств тегов и хабов
    """
    assert min_keywords >= 0
    assert limit is None or limit > 0
    
    corpus = []
    copied_keys = ('id','title','text')
    keywords_src_keys = ('tags','hubs')
    keywords_key = 'keywords'
    status_key = 'status'
    
    for fnm in os.listdir(HABR_POSTS_DIR):
        pid = fnm.split('.')[0]
        if pid.startswith('-'):
            # файл есть, статьи нет
            continue

        article = load_article(pid, HABR_POSTS_DIR, quiet=True)
        if not article or article[status_key] != 'ok':
            continue
            
        article_dict = dict()
        
        for k in copied_keys:
            if k in article:
                article_dict[k] = article[k]
        
        keywords = set()
        for k in keywords_src_keys:
            if k in article:
                keywords.update(filter_tags(article[k]))
        if len(keywords) < min_keywords:
            continue
            
        article_dict[keywords_key] = keywords
        
        corpus.append(article_dict)
        
        if limit is not None and len(corpus) >= limit:
            break
        
    
    return corpus


def load_cyberlen_corpus(limit=None, min_keywords=0, dir=CYBERLENINKA_ARTICLES_DIR):
    """
    load_cyberlen_corpus(limit=None, min_keywords=0)
      -> list(dict('id'->str, 'text'->str, 'title'->str, 'keywords'->[str], 'similar'->list))
    Similar: список названий и URL-ов похожих статей с исходной страницы
    """
    # ['year', 'url', 'text', 'article-ID', 'topic', 'title',
    # 'keywords', 'number', 'abstract', 'similar', 'Authors', 'status']
    assert min_keywords >= 0
    assert limit is None or limit > 0
    
    corpus = []
    copied_keys = ('article-ID','number','title','text', 'keywords', 'abstract', 'topic', 'Authors', 'similar')
    keywords_src_key = 'keywords'
    keywords_key = 'keywords'
    status_key = 'status'
    
    for fnm in os.listdir(dir):
        pid = fnm.split('.')[0]
        if pid.startswith('-'):
            # файл есть, статьи нет
            continue

        article = load_article(pid, dir, quiet=True)
        if not article or article[status_key] != 'ok':
            continue
            
        article_dict = dict()
        for k in copied_keys:
            if k in article:
                article_dict[k] = article[k]
        if keywords_src_key in article: # мы-то знаем, что ключ всегда присутствует :)
            article_dict[keywords_key] = filter_tags(article[keywords_src_key])
            if len(article_dict[keywords_key]) < min_keywords:
                continue
        elif min_keywords <= 0:
                continue
        corpus.append(article_dict)
        if limit is not None and len(corpus) >= limit:
            break

    return corpus


re_word = re.compile("[а-яё]+", re.I)

def validate_tag(tag):
    """
    Выкинуть:
       - слова из латиницы.
    Отсеять:
       - фразы короче 3 букв и содержащие подстроку "блог компании" (вернётся None).
    """
    if 'блог компании' in tag.lower():
        return None
    words = re.findall(re_word, tag)
    if words:
        words = ' '.join(words)
        if len(words) < 3:
            words = None
        return words
    return None

def filter_tags(tags):
    result = []
    for tag in tags:
        valid_tag = validate_tag(tag)
        if valid_tag:
            result.append(valid_tag)
    return result


class Article(object):
    """ Базовая Статья для хранения данных для извлечения и оценки качества извлечения терминов """
    def __init__(self, text="", title="No-Title", expert_terms=None):
        self.text = text
        self.title = title
        self.expert_terms = expert_terms
        
    def __repr__(self):
        return self.short_name()
        
    def __str__(self):
        return "<%s short-name='%s' text-size=%d>" % (
            self.__class__.__name__,
            self.short_name(),
            len(self.text)
        )
        
    def short_name(self):
        s = self.title
        if len(s) > 8:
            s = s[:8] + "."
        return s
        
    def expert_judgements(self):
        if not self.expert_terms:
            return []
        elif hasattr(self.expert_terms, "__iter__") and type(next(iter(self.expert_terms))) in (list,set,tuple):
            return self.expert_terms
        else:
            return [self.expert_terms]
            
            
class CyLenArticle(Article):
    """ Статья с портала Киберленинка """
    def __init__(self, article_dict):
# copied_keys = ('article-ID','number','title','text', 'keywords', 'abstract', 'topic', 'Authors', 'similar')
        keys_as_expert = ('keywords', 'abstract', 'title', 'topic',)
        expert = {k:article_dict[k] for k in keys_as_expert}
        super().__init__(article_dict['text'],
                         article_dict['title'],
                         expert)
        self.ID = article_dict['article-ID']
        
    def short_name(self):
        s = self.ID
        if len(s) > 12:
            s = s[:12]
        return s
        



if __name__ == '__main__':
	#  test
    cyberlen_corpus = load_cyberlen_corpus(dir=r"c:\Dev\SSearch\WebParsing\Cyberlen\articles")
    print(len(cyberlen_corpus))
    
    re_bib_caption = re.compile(r"^((?:[\w\s\n-z]*?$){,3})\s*^1\.", re.M|re.U)

    for a in cyberlen_corpus:
        t = a["text"]
        captions = re_bib_caption.findall(t)
        if captions:
            print('=====')
            for c in captions:
                if not c.strip():
                    continue
                print(c)
                print('-----')