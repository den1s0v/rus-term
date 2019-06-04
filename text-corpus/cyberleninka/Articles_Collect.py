"""
    Модуль выдает коллекцию объектов статей, отобранных из локальной базы данных
    (1)по похожести и (2)по авторам статьи, которая подана параметром.
    Количество статей ограничено обязательным параметром needCount.
    Импортировать из модуля функции:  get_SimilarArticles()  и  clearPreviewsCash()
"""
import os
import pickle
from cyberleninka_articles_v2 import getLastPathPart, str2hexid, fit_filename

ARTICLES_DIR = 'articles/'
TOPIC_DIR = 'topic/'
SavedPreviews = []
articles_nums = []
fileNames = []
fileNotFound = 0

def get_SimilarArticles(Article, checkFunc, needCount, workDir, recursive=False):
    """ Вход:
    1. Articles - словарь с одной (стартовой) статьёй
    2. checkFunc - функция проверки соответствия статьи на возможность включения (если True) в выходной список
    3. needCount - нужное кол-во статей в выходном списке
    4. workDir - рабочий директорий, в к-ром размещаются каталоги "articles" и "topic"
        Выход:
    Список статей, отобранных по полю похожести и по авторам входной Article
    Если другие статьи найдены не будут, будет возвращена только исходная статья.
    """
    global articles_nums
    loadPreviews(Article['topic'], workDir)
    out_articles = []
    if not recursive:
        out_articles.append(Article)
        articles_nums = [Article["number"]]
        fileNames = []
        fileNotFound = 0
    
    # Поиск статей по полю похожести
    if 'similar' in Article and Article["similar"]:
        for a_s in Article['similar']:
            articleID = getLastPathPart(a_s['similar_url'])
            articleDict = getArticle(articleID, workDir)
            if not articleDict  or  articleDict["number"] in articles_nums  or  not checkFunc(articleDict):
                continue
            
            out_articles.append(articleDict)
            articles_nums.append(articleDict["number"])
            print('Добавлено по "similar": %d' % articleDict["number"])
            
            if len(out_articles) >= needCount:
                break

        if len(out_articles) >= needCount:
            return out_articles

    # Поиск статей по авторам
    if 'Authors' in Article and Article["Authors"]:
        article_Authors = list( map( lambda param: param.strip() , Article['Authors']) )
        for articlePreview in SavedPreviews:
            curr_Authors = list( map( lambda param: param.strip() , articlePreview['Authors']) )
            for a_a in article_Authors:
                if a_a in curr_Authors:

                    articleID = getLastPathPart(articlePreview['url'])
                    articleDict = getArticle(articleID, workDir)
                    if not articleDict  or  articleDict["number"] in articles_nums  or  not checkFunc(articleDict):
                        continue            

                    out_articles.append(articleDict)
                    articles_nums.append(articleDict["number"])
                    print('Добавлено по "Authors": %d' % articleDict["number"])
                    
                    break

            if len(out_articles) >= needCount:
                return out_articles
                
    #Рекурсивный запуск:
    listLen = len(out_articles)
    if listLen > 1 and listLen < needCount:
        currLen = listLen
        # for i in range(listLen):  # нерастущая рекурсия
            # out_articles += get_SimilarArticles(out_articles[i], checkFunc, needCount-currLen, workDir, recursive=True)
        for currArt in out_articles:    # растущая рекурсия
            out_articles += get_SimilarArticles(currArt, checkFunc, needCount-currLen, workDir, recursive=True)
            currLen = len(out_articles)
            if currLen >= needCount:
                break
    
    return out_articles

def clearPreviewsCash():
    if not SavedPreviews:
        return
    SavedPreviews = []

def loadPreviews(Previews_Topic, workDir):
    global SavedPreviews
    if SavedPreviews and SavedPreviews[0]["topic"] == Previews_Topic:
        return
    if not Previews_Topic:
        return
    fname = os.path.join(workDir + '/', TOPIC_DIR, Previews_Topic + '.pkl')
    fname = fit_filename(fname)
    if os.path.exists(fname):
        with open(fname, mode='rb') as f:
           SavedPreviews = pickle.load(f)
    else:
        print('Не найден файл со списком статей категории  "' + fname + '"')

def getArticle(articleID, workDir):
    global fileNames, fileNotFound
    article = False
    shortfname = str2hexid(articleID)
    if shortfname in fileNames:
        return article
    else:
        fileNames.append(shortfname)
    fname = os.path.join(workDir + '/', ARTICLES_DIR, shortfname + '.pkl')
    fname = fit_filename(fname)
    if os.path.exists(fname):
        with open(fname, mode='rb') as f:
           article = pickle.load(f)
    else:
        fileNotFound += 1
        print('%d. Не найден файл со статьей  ' % fileNotFound, '"'+fname + '"')
        with open('Articles_not_Found.txt', mode='a', encoding='utf-8') as wf:
            wf.write(articleID + '\n')
    return article


if __name__ == '__main__':

    loadPreviews('Приборостроение', '.')
    articlesCollection = get_SimilarArticles(SavedPreviews[17], lambda p: True, 20, '.')

    print('Articles number found:')
    for i, a in enumerate(articlesCollection):
        print(a["number"], end='\t')
        if i % 10 == 9:
            print()
    print()
