# coding=utf-8

import re

from text_utils import *
from rule.rule_utils import get_definition_patterns_extended, T_LAT
from extract_terms import copyTerm, makeTerm
from eval_utils import Evaluator, are_patterns_match

DEF_PTT_PATH = 'rule/definition_patterns.txt'


re_word_sep = re.compile(r'\W+')

def split_pattern(def_ptt):
    """ Remove all non-alphanum chars & split """
    return list(filter(None, re_word_sep.split(def_ptt)))

def normalize_pattern(def_ptt):
    """ Remove all non-alphanum char """
    return re_word_sep.sub(' ', def_ptt).strip()
    
ev = None

def init_module(morph):
    global ev
    ev = Evaluator(morph=morph)

def lemmatize_def_ptt(def_ptt):
    assert ev, "Run `init_module(morph)` with Pymorphy2.Parser instance first!"
    return ev.lemma_pattern(def_ptt)

def lemmatize_term(term):
    term.lemmas = lemmatize_def_ptt(term.normalized)
    return term

def combine_terms_by_length(terms):
    """ 
    returns: dict(len -> combined_term)
    где combined_term - объект-термин, содержащий все упорядоченные леммы терминов одной длины len
    """ 
    res_dict = dict()
    for t in terms:
#         print(t, '...')
        L = len(t.words)
        if L not in res_dict:
            res_dict[L] = copyTerm(t)
            res_dict[L].lemmas = t.lemmas
            print('add phrase of length:', L)
        else:
            base = res_dict[L]
            updated_lemmas = []
            for tl,bl in zip(t.lemmas, base.lemmas):
#                 if 'стек' in t.normalized:
#                     print(tl, bl)
                updated_lemmas.append(bl | tl)
            base.lemmas = tuple(updated_lemmas) # set updated back
            
    
    return res_dict


def full_comb(k, items):
    """ Полная перестановка n^k вариантов, где n = len(items) """
    assert k>0 and items
    items = list(items)
    n = len(items)
    if k == 1:
        return [(x,) for x in items]
    else:
        res_list = []
        tails = full_comb(k-1, items)
        for x in items:
            for t in tails:
                res_list.append((x, *t))
        return res_list
        
        
def concat_terms(*terms):
    assert terms
    if len(terms) == 1 and type(terms[0]) in (list,set,tuple):
        terms = terms[0]
    words = [w for t in terms for w in t.words]
    lemmas = tuple([L for t in terms for L in t.lemmas])
    normalized = (' '.join([t.normalized.strip() for t in terms])).strip()
    t = makeTerm(words=words, normalized=normalized)
    t.lemmas = lemmas
    return t
    
def emptyTerm():
    t = makeTerm()
    t.lemmas = ()
    return t


def def_ptt2template_terms(def_ptt):
    """ Шаблонизировать новые объекты терминов расширенными
    паттернами дефиниций и заполнить для них леммы.
    Возвращает кортеж:
     (
         list[Строка "T" для подстановки термина, ИЛИ объект Term для слов шаблона],
         int - количество подстановочных "T"
     )
    Пример:
tt = def_ptt2template_terms(def_patterns[8])
fld = 'lemmas'
print(tt[1], "Ts in pattern")
print([getattr(t,fld) if hasattr(t,fld) else t for t in tt[0]])
    """    
    # формирование шаблона для заполнения терминами ...
    ptt_parts = split_pattern(def_ptt)
    ptt_terms = [] # это шаблон
    t_toks = [] # в
    T_count = 0
    
    def add_words_as_term(words,arr):
        t = makeTerm(words=list(words), normalized=' '.join(words))
        arr.append(lemmatize_term(t))
        
    for w in ptt_parts:
        if w == T_LAT:
            if t_toks:
                add_words_as_term(t_toks,ptt_terms)
                t_toks.clear()
            ptt_terms.append(T_LAT) # term placeholder
            T_count += 1
        else:
            t_toks.append(w)
    if t_toks:
        add_words_as_term(t_toks,ptt_terms)
        t_toks.clear()

    return ptt_terms, T_count
    
def fill_def_ptts_with_terms(def_ptts,terms):
    """ Шаблонизация def-паттернов иЗаполнение их "настоящими" терминами
    (для всех комбинаций длин терминов). 
    Возвращается список терминов с дополнительным полем term_inidices, в
    котором -- список начальных и конечных индексов слов, относящихся к подставленному термину.
    
    ПРИМЕР с возможным выводом (где термины - 
        "объект", "клиентский код", "поведенческий паттерн проектирования", 
        - обозначны индексами в удобном для формирования slice отсчёте (i, j+1)):
>>> fts = fill_def_ptts_with_terms(def_patterns, my_chapter.get_term_candidates())
>>> print(len(fts), "total")
>>> print([(t.normalized, t.term_inidices) for t in fts[::20]])
add phrase of length: 1
add phrase of length: 2
add phrase of length: 3
add phrase of length: 5
add phrase of length: 4
add phrase of length: 6
516 total 
[('объект это', [(0, 1)]),
 ('клиентский код это поведенческий паттерн проектирования', [(0, 2), (3, 6)]),
 ...
 ('термином поведенческий паттерн проектирования', [(1, 4)])]
    """
    cmb_ts = combine_terms_by_length(terms)
    
    res_list = []  # terms ready to match against a sentence
    # дополнительным полем `term_inidices` - индексы слов, принадлежащих терминам
    for ptt in def_ptts:
        tmpl, nT = def_ptt2template_terms(ptt)
        for cmb in full_comb(nT, cmb_ts.keys()):
            terms2concat = []
            t_indices = []
            cmb = iter(cmb)
            next_i = 0
            for t in tmpl:
                if type(t) is str and t == T_LAT:
                    t_len = next(cmb)
                    terms2concat.append(cmb_ts[t_len])
                    t_indices.append( (next_i, next_i+t_len) )
                    next_i += t_len
                else:
                    terms2concat.append(t)
                    next_i += len(t.words)
#                     print(t.normalized, ":", t.words)
                    
            tc = concat_terms(terms2concat)
            tc.term_inidices = t_indices
            res_list.append(tc)
    del cmb_ts
    return res_list


def match_terms_against_chapter(chapter, filled_def_ptts):
    """ Сопоставить заполненные шаблоны filled_def_ptts
    предложениям Главы chapter.
    Возвращается список кортежей, в каждом из которых:
        [0]: term_as_used:
            список строк - словоупотребления, совпавшие с одним из терминов по одному из паттернов,
        [1]: pattern_context_as_used:
            список строк - контекст словоупотреблений (все слова совпадения с паттеном), или "<same-context>", если термины не содержат поля term_inidices.
    """
    assert chapter and filled_def_ptts
    
    match_list = []  # elem: (term_as_used, pattern_context_as_used)
    
    for s in chapter.sentence_list:
        for t in filled_def_ptts:
            for words in s.match_term(t):
                if hasattr(t, "term_inidices"):
                    # известна раскладка терминов в паттерне
                    for st,end in t.term_inidices:
                        match_list.append( (words[st:end], words) )
                else:
                    match_list.append( (words, "<same-context>") )
    return match_list


def match_terms(matched_words_list, known_terms):
    """ Сопоставить находки с известными терминами.
    Возвращает: словарь dict{known_term -> mentions_count}
    matched_words_list - список фраз, в каждой которых каждое слово является отдельным элементом списка/кортежа
    """
    res_dict = dict()
    
    for mws in matched_words_list:
        matched_lemma_ptt = lemmatize_def_ptt(" ".join(mws))
        for t in known_terms:
            if are_patterns_match(matched_lemma_ptt, t.lemmas):
                if t not in res_dict:
                    res_dict[t] = 1
                else:
                    res_dict[t] += 1
    return res_dict

# найти самые удачные шаблоны дефиниций
def filled_ptt_term2ptt(fpt):
    """ Заменяет подставленные термины обратно на "T". Возвращает строку. 
    fpt - filled def-pattern - объект Term c полем term_inidices """
    words = list(fpt.words)
    for st,end in reversed(fpt.term_inidices):
        words[st:end] = [T_LAT]
    return " ".join(words)

def rank_def_patterns(matched_words_list, filled_def_ptts):
    """ Сопоставить находки с самими паттернами """
    res_dict = dict()
    
    for mws in matched_words_list:
        matched_lemma_ptt = lemmatize_def_ptt(" ".join(mws))
        for ft in filled_def_ptts:
            if are_patterns_match(matched_lemma_ptt, ft.lemmas):
                ptt = filled_ptt_term2ptt(ft)
                if ptt not in res_dict:
                    res_dict[ptt] = 1
                else:
                    res_dict[ptt] += 1
    return res_dict