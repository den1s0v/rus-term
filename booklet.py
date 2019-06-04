# coding=utf-8

import itertools

from text_utils import *
from extract_terms import copyTerm

STOPWORDS_PATH = './'+'text-corpus/stopwords.txt'



def interleave_lists(*lists):
    """ Returns plain list of lists`s elements.
        Elements are positioned by each list`s order 
        and order of lists. 
        Example:
        >>> lists = [[1,2,3],[11,22,33,44],[111,222,333,444,555]]
        >>> interleave_lists(*_lists)
        [1, 11, 111, 2, 22, 222, 3, 33, 333, 44, 444, 555]
        """
    tuples = list(itertools.zip_longest(*lists, fillvalue=None))
    cs = list(filter(None, [t for ts in tuples for t in ts]))
    return cs
    

def merge_similar_terms(term_list, quiet=False):
    """ Простое слияние терминов с одинаковым .normalized полем. """ 
    res_list = []
    term_set = set(term_list)
    not quiet and print(len(term_set), 'unique terms out of', len(term_list), 'terms.')
    for i,t in enumerate(term_set):
        similar = [T for T in term_list if T==t]
        not quiet and i%1000==0 and print(i,'.',str(t),":", list(map(str,similar)))
        if len(similar) == 1:
            res_list.append(similar[0])
        elif len(similar) > 1:
            T = copyTerm(similar[0])
            T.lemmas = similar[0].lemmas
            T.count = sum([e.count for e in similar])
            res_list.append(T)
    return res_list
    
def text2collocations(text, max_N = 3, uniqualize=False):
    """ Из слов текста длинее 1 буквы строится набор кортежей-коллокаций слов, 
        каждая коллокация длиной от 1 до max_N слов.
        Предварительно текст делится на предложения, т.обр. 
        коллокации не переходят через границу предложений.
        Если параметр uniqualize истинен, то коллокации-дубликаты 
        будут удалены, а порядок кортежей в вохвращаемом списке станет случайным. 
        Пример:
        
        text2collocations("One,two, Three, Четыре, пять? Я иду ИСКАТЬ! OnE,TWO, ...", max_N=5, uniqualize=1)
        """
    w_tuple_list = []
    sentences = te.extract_sentences_from_text(text)
    s_words = [
        [w.lower() for w in te.sentence_word_re.findall(line) if len(w)>=2] # минимум 2 буквы в слове
        for line in sentences
    ]
    sentences.clear()
    max_N = min(max_N, max([len(ws) for ws in s_words]))
    for n in range(1, max_N+1):
        for w_list in s_words:
            for p in range(len(w_list)+1-n):
                w_tuple_list.append( tuple(w_list[p:p+n]) )
    if uniqualize:
        w_tuple_list = list(set(w_tuple_list))
    return w_tuple_list
    
def ch2test_sets(ch):
    """ Построение из "article"-словаря КиберЛенинки тестового набора для оценки качества извлечения терминов """
    return {
        "title"    : text2collocations(ch.user_data["title"], max_N=4, uniqualize=True),
        "keywords" : ch.user_data["keywords"],
        "abstract" : text2collocations(ch.user_data["abstract"], max_N=5, uniqualize=True),
#         "topic"    : text2collocations(ch.user_data["topic"], max_N=4, uniqualize=True),
    }
    
# STOPWORDS_PATH = '/home/user/dev/'+'texts/stopwords.txt'
STOPWORDS_PATH = './'+'text-corpus/stopwords.txt'

class Booklet(object):
    """ Книга, брошюра. Последовательность Глав (класс Chapter). """
    def __init__(self, ):
        self.chapter_list = []
        self.__term_candidates_cache = None
        
    def at(self, i):
        """ get chapter at index `i` """
        return self.chapter_list[i]

    def __len__(self):
        return self.size()

    def size(self):
        return len(self.chapter_list)
        
    def word_count(self):
        return sum([ch.word_count() for ch in self.chapter_list])
        
    def sentence_count(self):
        return sum([ch.size() for ch in self.chapter_list])
        
    def count_of(self, word):
        """return count of word(s) / term(s) found within sll chapters"""
        assert self.chapter_list
        return sum([ch.count_of(word) for ch in self.chapter_list])
        
    def get_stopwords(self):
        """return set of stopwords"""
        assert self.chapter_list
        return self.chapter_list[0].get_stopwords()
        
    def add_chapter(self, title='Untitled', text=None, user_data=None):
        
        et_obj = None
        
        if self.chapter_list:
            et_obj = self.chapter_list[0].get_extract_terms()
            start_pos = self.chapter_list[-1].sentence_list[-1].endpos
            start_pos.word += 1
            start_pos.sentence += 1
        else:
            start_pos = te.Position() # begin of text
            
        ch = te.Chapter(title=title, extract_terms_instance=et_obj)
        if text and type(text) is str:
            ch.load_text(text, start_position=start_pos)
        if len(ch.sentence_list) <= 0:
            return
        ch.user_data = user_data
        self.chapter_list.append(ch)

    def prepare_terms(self):
        """Extract nominal groups from the text for all chapters"""
        for ch in self.chapter_list[:]:
            print(ch.title, "...")
            try:
                ch.prepare_terms(stopwords_file=STOPWORDS_PATH, quiet=True)
            except AssertionError:
                self.chapter_list.remove(ch)

    def clear_cache(self):
        " reset cached data if any for all chapters "
        for ch in self.chapter_list:
            ch.clear_cache()
    
    def get_term_candidates(self, limit=None):
        """return term candidates list optionally
            cropped with limit for all chapters.
            Terms are positioned by total frequency (desc.). """
        if self.__term_candidates_cache:
            return self.__term_candidates_cache[:limit]

        cs = [ch.get_term_candidates() for ch in self.chapter_list]
        cs = interleave_lists(*cs)
        cs = merge_similar_terms(cs)[:limit]
        cs.sort(key=lambda t:-t.count)
        self.__term_candidates_cache = cs
        return cs

    def find_terms(self, substr, limit=None, exact_match=False):
        """ получить термы по полному совпадению или по части слова """
        ts = [ch.find_terms(substr,exact_match=exact_match)
              for ch in self.chapter_list]
        return interleave_lists(*ts)[:limit]
    
    def chapters_with_term(self, term, min_entries=1, min_score=0):
        """ Returns list(of tuples: (Chapter, score)).
            Найти главы (Chapter`ы) с указанным(-и) 
            термином(-ами) и отосртировать их по 
            убыванию плотности встречаемости термина.
            Показатель score показывает, насколько чаще терм встречается в
            главе, чем по коллекции.
            Если score больше 1, то термин упоминается в главе 
            чаще, чем по коллекции, если меньше 1 - то реже.
            Если порог min_entries указан, то в выдачу 
            попадут только те (Chapter`ы) с min_entries 
            и больше вхождений термина. """
        assert min_entries > 0
        chs = [(ch, ch.count_of(term)) for ch in self.chapter_list]
        chs = [tpl for tpl in chs  if tpl[1] >= min_entries]
#         Nword = self.count_of(term)
        Nword = sum([n for _,n in chs]) # этот термин по всей коллекции
        Nchpt = self.size()
        NwordsTotal = self.word_count()
        chs = [(ch, n/Nword*Nchpt * ch.word_count()/NwordsTotal*Nchpt) for ch,n in chs]
        
        chs = [tpl for tpl in chs  if tpl[1] >= min_score]
        chs.sort(key=lambda e:-e[1])
        return chs
        
    def df(self, term):
        """ DF - document frequency over collection
            Частота появления термина в документах коллекции """
        return len(self.chapters_with_term(term))
        
    def term_stdev_rank(self, term, parts):
        """
        Получить вес термина как среднеквадратическое отклонение его профиля, сжатого до `parts` фрагментов.
        Каждый chapter даёт целое число частей.
        Вес многословных терминов повышается кратно количеству слов.
        В случае, если `term` - это list / set терминов,
        в подсчёте среднеквадратического отклонения участвуют все термины,
        а длина термина определяется по первому термину из списка.
        """
        if type(term) in (list, set):
            t = next(iter(term))
        else:
            t = term
        assert hasattr(t, "normalized") and hasattr(t, "words")
        
        # find out 'parts' value for each chapter in the Booklet; Sum should be equal to parts param.
        N_sents = self.sentence_count() # total count of sentences in the Booklet
        parts4chs = [max(1, round(parts*ch.size()/N_sents)) for ch in self.chapter_list]
        
        full_profile = pd.Series()
        for i,ch in enumerate(self.chapter_list):
            t_series = ch.compress_profile(parts4chs[i], ch.profile4word_or_family(term) )
            full_profile = pd.concat([full_profile, t_series] )
#                                      ignore_index=True,
#                                      verify_integrity=False)
        
        rank = full_profile.std() * len(t.words)  # повышаем вес многословных терминов
        del t_series
        del full_profile
        return rank
    
    def rank_candidates_stdev(self,parts=None, min_count=1):
        parts = parts or self.size()
        assert parts > 0, "Positive values only allowed. Provided: %d" % parts

        ranks = []
        for t in self.get_term_candidates():
            if t.count < min_count or len(t.normalized) < 2:
                continue
            r = self.term_stdev_rank(t, parts)
            ranks.append( (t, r) )

        ranks.sort(key=lambda e:-e[1])        
        return ranks
    
    def relate_ranking_by_chapters(self, ranks):
        """ Соотносит термины из ранжированного списка терминов релевантным главам.
            Returns:
                list[ 
                     tuple( chapter_obj, rank_list[
                             tuple(Term, score)
                         ] )
                    ]
             ranks: list[ tuple(Term, score) ]       
        """
#         ranks = self.rank_candidates_stdev(parts=prt, min_count=5)

        ranks_by_ch = {}
        for t,t_sc in ranks:
            ch_sc_list = self.chapters_with_term(t, min_score=1)
            for ch,ch_sc in ch_sc_list:
                ch_i = self.chapter_list.index(ch)
#                 print(ch_i)
                elem_tuple = (t,t_sc*ch_sc)
                if ch_i in ranks_by_ch:
                    ranks_by_ch[ch_i].append(elem_tuple)
                else:
                    ranks_by_ch[ch_i] = [elem_tuple]
        res_list = []
        for i in ranks_by_ch:
            # print(i, bl0.at(i).title)
            ranks_by_ch[i].sort(key=lambda e:-e[1])
            res_list.append( (self.at(i), ranks_by_ch[i]) )
        ranks_by_ch.clear()
        return res_list
        
        