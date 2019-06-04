# coding=utf-8

from collections import namedtuple
import pickle
import re

import pymorphy2

 
EvalData = namedtuple('EvalData', 'name test ranked alg title expert')


def make_eval_data(ranked_terms, test_terms, name='noname', alg_name='no-alg', text_title='untitled', expert_name="no-expert"):
    """
    ranked_terms:
        упорядоченный по убыванию список терминов (строк), ранжированный некоторым методом/алгоритмом
    test_terms:
        неупорядоченный список/множество эталонных терминов (строк), предназначенный для проверки ранжированного списка ranked_terms
    name [obsolete?]:
        название/имя собственное метода/алгоритма (не изменяется при смене набора обрабатываемых данных)
    """
    return EvalData(
        name=name,
        test=test_terms,
        ranked=ranked_terms,
        alg=alg_name,
        title=text_title,
        expert=expert_name
    )

def map2short_labels(strings, capitalize=False):
    """ Takes list of string and returns their mapping
        to unambiguously cropped correspondings of them.
    """
    def case(s):
        return s.upper() if capitalize else s
    Nuniq = len(set(strings))
    for L in range(1,10):
        test_set = {case(s[:L]) for s in strings}
        if len(test_set) == Nuniq:
            break
    else:
        L = max([len(s)] for s in strings)
    
    return {s: case(s[:L]) for s in strings}


_non_id_re = re.compile(r"[\W]+", re.I | re.UNICODE)
_wsps_re = re.compile(r"\s+", re.I | re.UNICODE)

def simplify_name(string):
    """ Removes all non-word (alphadigit_) chars from string (chars in the middle are replaced with "_").
        Example:
     >>> simplify_name("'patt#ernS+Y" )
     'patt_ernS_Y'
    """
    string = _non_id_re.sub(" ", string).strip()
    string = _wsps_re.sub("_", string)
    return string


class RankingEvalData(object):
    """ Класс для хранения данных для оценки качества извлечения терминов. Public properties:
        .subject : object
            - Любой объект (обозначающий исходный текст), имеющий метод __repr__(), возвращающий короткую строку - имя текста
        .rankings : dict("ALG-name" -> list[str])
            - Ранжированные некими алгоритмами термины
        .test_sets : dict("expert-name" -> list_or_set[str or tuple_of_strings])
            - Размеченные некими экспертами наборы эталонных терминов
    """
    def __init__(self, subject="UNKN", rankings={}, test_sets={}):
        self.subject = subject
        self.rankings = rankings
        self.test_sets = test_sets
        self.short_name_limit = 8
    
    def short_name(self):
        s = repr(self.subject) or "NoTitle"
        return simplify_name(s)[:self.short_name_limit]
        
    def clear(self):
        self.subject = 'cleared!'
        self.rankings.clear()
        self.test_sets.clear()
        
    def to_EvalData_list(self, use_short_labels=True):
        ed_list = []
        alg_nms = list(self.rankings.keys())
        exp_nms = list(self.test_sets.keys())
        if use_short_labels:
            alg_nms = map2short_labels(alg_nms, capitalize=True)
            exp_nms = map2short_labels(exp_nms, capitalize=True)
        else:
            alg_nms = {nm:nm for nm in alg_nms}
            exp_nms = {nm:nm for nm in exp_nms}
        
        for alg, rnk in self.rankings.items():
            for exp, exp_set in self.test_sets.items():
                ed = make_eval_data(rnk, exp_set, 
                                    name="%s-%s-%s" % (self.short_name(),alg_nms[alg],exp_nms[exp]),
                                    alg_name=alg_nms[alg],
                                    text_title=self.short_name(),
                                    expert_name=exp_nms[exp]
                                   )
                ed_list.append(ed)
        return ed_list
    
    def get_filename(self):
        alg_nms = map2short_labels(list(self.rankings.keys()), capitalize=True).values()
        exp_nms = map2short_labels(list(self.test_sets.keys()), capitalize=True).values()
        return "%s_%s-%s_RaED.pkl" % (
            self.short_name(),
            "".join(alg_nms), # len(self.rankings),
            "".join(exp_nms), # len(self.test_sets),
        )


def are_patterns_match(ptt1, ptt2):
    """
    are_patterns_match(ptt1, ptt2) -> bool
    Возвращает True, если для паттернов:
       - совпадают длины (кол-ва слов) и 
       - для каждого есть совпадающие (общие) леммы

    ptt1, ptt2 (both are tuples):
        Кортеж множеств по количеству слов во фразе.
        Каждое множество (set) содержит леммы (начальные формы слова).
    """
    # совпадают длины и для каждого есть совпадающие (общие) леммы
    return len(ptt1) == len(ptt2) and all([ptt1[i].intersection(ptt2[i]) for i in range(len(ptt1))])


def F1(precision,recall):
    if precision+recall <= 0:
        return 0
    else:
        return 2*precision*recall / (precision+recall)



class Evaluator(object):
    def __init__(self, morph=None):
        self.pymorphy2_morph = None # синглтон для анализатора (не нужно загружать, если не будем использовать)
        self.set_morph(morph)
        
        self._lemma_pattern_cache = {}
        self._relevance_cache = {}
        

    def set_morph(self, morph):
        if morph and hasattr(morph, 'parse'):
            self.pymorphy2_morph = morph
        else:
            print("Warning. Evaluator.set_morph(): invalid morph object! Provided: %s" % str(type(morph)))
            
    def get_morph(self):
        if not self.pymorphy2_morph:
            self.pymorphy2_morph = pymorphy2.MorphAnalyzer() # загрузить анализатор
        return self.pymorphy2_morph

    def clear_cahe(self):
        self._lemma_pattern_cache.clear()
        self._relevance_cache.clear()

    def lemma_pattern(self, word):
        """
        lemma_pattern(word) -> tuple of sets(each set of lemmas)
        
        word (str):
            Слово или фраза (несколько слов, разделённых пробелами)
        returns:
            Кортеж множеств по количеству слов во фразе.
            Каждое множество (set) содержит вероятные начальные формы слова.
        """

        if word in self._lemma_pattern_cache:
            return self._lemma_pattern_cache[word]
        
        # гипотезы морфологического разбора
        hyps = [self.get_morph().parse(str(w)) for w in word.split()]
        # кортеж из множеств лемм-гипотез
        lemmas_tuple = tuple([set([p.normal_form for p in hyp]) for hyp in hyps])
        # update cache
        self._lemma_pattern_cache[word] = lemmas_tuple
        return lemmas_tuple
        
    def relevance(self, word, expert_term):
        """
        relevance(self, word, expert_term) -> float[0..1]
        Compare words or phrases, maybe particulary.
        
        word (str):
            Слово или фраза (несколько слов, разделённых пробелами)
        expert_term (str или tuple):
            Слово, фраза (несколько слов, разделённых пробелами) или кортеж слов
        """
        if (word, expert_term) in self._relevance_cache:
            return self._relevance_cache[(word, expert_term)]
        
        # update cache
        def update_cache_proxy(result):
            self._relevance_cache[(word, expert_term)] = result
            return result

        
        if type(expert_term) is tuple:
            full_et = ' '.join(expert_term)
            if word == full_et:
                return update_cache_proxy(1)
        else:
            full_et = expert_term
        ptt_w = self.lemma_pattern(word)
        ptt_et = self.lemma_pattern(full_et)
        if are_patterns_match(ptt_w, ptt_et):
            return update_cache_proxy(1)
        
        # анализируем совпадения отдельных слов
        n_w = len(ptt_w)
        n_et = len(ptt_et)
        for m in range(n_w, 0, -1):
            for i in range(0, n_w-m+1):
                for j in range(0, n_et-m+1):
                    subptt_w  = ptt_w [i:i+m]
                    subptt_et = ptt_et[j:j+m]
                    if are_patterns_match(subptt_w, subptt_et):
                        v = (m/n_w) * (m/n_et)  # совпавшая доля слов от обеих фраз
                        return update_cache_proxy(v)
        # так ничего и не совпало
        return update_cache_proxy(0)
        
    def f1_at_k(self, k, eval_data_list, quiet=False):
        """
        F1 at top k - средняя мера F1 из первых k ранжированных терминов.
        F-мера (F1 score) представляет собой совместную оценку точности и полноты. Формула:
            F-мера = 2 * Точность * Полнота / (Точность + Полнота)
        returns dict:
            {
                "<name_1>" : f1
                "<name_2>" : f1
                ...
            }
        где:
            "<name_N>" - строка с именем алгоритма,
            recall - число типа float - полнота (recall) для указанного k
        """
        assert k > 0
        assert eval_data_list
        
        calc_list = []
        res_dict = {}
        relevance_func = lambda word, expert_term:self.relevance(word, expert_term)
        for ed in eval_data_list:
            if not quiet:
                print(ed.name,end='... ')
            ev = RankingEvaluator(ed,  relevance_func)
            ev.calc_relevence_list_at_k( k )
            calc_list.append( (ed.alg, ev.precision_at_k(k), ev.recall_at_k(k)) )
            
        for name in set([c[0] for c in calc_list]):
            calc = [c[1:3] for c in calc_list  if c[0] == name]
            f1 = [F1(pr[0],pr[1]) for pr in calc]
            res_dict[name] = sum(f1) / len(f1)
            
        return res_dict

    def mean_recall_at_k(self, k, eval_data_list, quiet=False):
        """
        mean recall at top k - средняя полнота из первых k ранжированных терминов
        returns dict:
            {
                "<name_1>" : recall
                "<name_2>" : recall
                ...
            }
        где:
            "<name_N>" - строка с именем алгоритма,
            recall - число типа float - полнота (recall) для указанного k
        """
        assert k > 0
        assert eval_data_list
        
        calc_list = []
        res_dict = {}
        relevance_func = lambda word, expert_term:self.relevance(word, expert_term)
        for ed in eval_data_list:
            if not quiet:
                print(ed.name,end='... ')
            ev = RankingEvaluator(ed,  relevance_func)
            ev.calc_relevence_list_at_k( k )
            calc_list.append( (ed.alg, ev.recall_at_k(k)) )
            
        for name in set([c[0] for c in calc_list]):
            calc = [c[1] for c in calc_list  if c[0] == name]
            res_dict[name] = sum(calc) / len(calc)
            
        return res_dict

    def ap_at_ks(self, ks, eval_data_list, quiet=False):
        """
        ap@k - average_precision at top k
        returns dict:
            {
                k_1: {
                    "<name_1>" : ap@k
                    "<name_2>" : ap@k
                    ...
                    },
                k_2: {
                    "<name_1>" : ap@k
                    "<name_2>" : ap@k
                    ...
                    },
                ...
            }
        где:
            k_N - целое k из списка ks (могут присутствовать не все k из ks, если кол-во ranked меньше такого k),
            "<name_N>" - строка с именем алгоритма,
            ap@k - число типа float - average_precision для указанного k,
        """
        assert ks
        assert min(ks) > 0
        assert eval_data_list
        
        k_max = max(ks)
        res_dict = {}
        ev_dict = {}
        relevance_func = lambda word, expert_term:self.relevance(word, expert_term)
        for ed in eval_data_list:
            if not quiet:
                print(ed.name,end='... ')
            if len(ed.ranked) < k_max:
                curr_k_max = max([k for k in ks if k <= len(ed.ranked)])
            else:
                curr_k_max = k_max
            ev = ev_dict[ed.alg] = RankingEvaluator(ed,  relevance_func)
            ev.calc_relevence_list_at_k( curr_k_max )
            
        for k in ks:
            if len(ed.ranked) < k:
                continue
            res_dict[k] = {}
            for name,ev in ev_dict.items():
                res_dict[k][name] = ev.average_precision_at_k(k)
            if not quiet:
                print(k,end=' ')
                
        for ev in ev_dict.values():
            del ev
            
        return res_dict

    def map_at_ks(self, ks, eval_data_list, quiet=False):
        """
        map@k - mean average_precision at top k.
        eval_data_list:
            может и должно содержать элементы с одним и тем же name (для разных наборов данных),
            для нахождения среднего ap@k по ним.
        returns dict:
            {
                "<name_1>": {
                    k_1 : {
                            "map": map@k,
                            "count": int_COUNT
                        }
                    k_2 : {
                            "map": map@k,
                            "count": int_COUNT
                        }
                    ...
                    },
                "<name_2>": {
                    k_1 : {
                            "map": map@k,
                            "count": int_COUNT
                        }
                    k_2 : {
                            "map": map@k,
                            "count": int_COUNT
                        }
                    ...
                    },
                ...
            }
        где:
            k_N - целое k из списка ks (могут присутствовать не все k из ks, если кол-во ranked меньше такого k),
            "<name_N>" - строка с именем алгоритма,
            map@k - число типа float - average_precision для указанного k,
            int_COUNT - целое кол-во "наблюдений" ap@k; N в формуле map@k = (1 / N) * SUM[ap@k].
        """
        assert ks
        assert min(ks) > 0
        assert eval_data_list
        
        ap_dict = {}
        # relevance_func = lambda word, expert_term:self.relevance(word, expert_term)
        for ed in eval_data_list:
            if ed.alg not in ap_dict:
                ap_dict[ed.alg] = []
            if not quiet:
                print(ed.name,end='... ')
            # получить ap@k только для этого ранжированного списка
            res = self.ap_at_ks(ks, [ed], quiet=True)
            ap_dict[ed.alg].append(res) # собрать все оценки каждого метода воедино
            
        res_dict = {}
        
        for name in ap_dict:
            count = len(ap_dict[name])  # count - кол-во различных проверочных рядов, учтённых в расчёте map@k (больше - лучше)
            if not quiet and count <= 4:
                print("map@k warn: There is only %d observation(s) for ALG '%s' !"%(count, name))
            res_dict[name] = {}
            for k in ks:
                ap_list = [r[k][name] for r in ap_dict[name] if k in r]
                count = len(ap_list)  # кол-во "наблюдений" ap@k
                if count == 0:
                    # не собрано таких k из данных
                    continue
                res_dict[name][k] = { "map": sum(ap_list) / count, "count":count }
            
        return res_dict


        
class RankingEvaluator(object):
    def __init__(self, eval_data, relevance_func):
        assert eval_data
        assert relevance_func and hasattr(relevance_func, '__call__')
        
        self.relevance = relevance_func
        self.data = eval_data
        self.round_relevance = True
        self.judged = None
        self.max_k = 0  #  не рассчитано ещё
        
    def calc_relevence_list_at_k(self, k):
        assert 0 < k <= len(self.data.ranked)
        self.max_k = max(self.max_k, k)
        
        self.judged = [0] * k
        for i in range(k):
            judge = max([self.relevance(self.data.ranked[i], et) for et in self.data.test])
            if self.round_relevance:
                # округлить для установки в {0,1}
                judge = round(judge)
            self.judged[i] = judge
    
    def precision_at_k(self, k):
        assert 0 < k <= self.max_k
        assert self.judged
        n_relevant = sum([self.judged[i] for i in range(0,k)])
        return n_relevant / k
    
    def recall_at_k(self, k):
        assert 0 < k <= self.max_k
        assert self.judged
        n_relevant = sum([self.judged[i] for i in range(0,k)])
        return n_relevant / len(self.data.test)
    
    def average_precision_at_k(self, k):
        assert 0 < k <= self.max_k
        assert self.judged
        summ = sum([self.precision_at_k(i) for i in range(1,k+1)])
        return summ / k
    
# names = ranked_terms.keys() # ["freq","stdev"]
# print(names)
# eval_data_list = [make_eval_data(ranked_terms[nm], expert_terms, nm) for nm in names]


def load_data(filepath, quiet=False):
    try:
        with open(filepath, mode='rb') as f:
            return pickle.load(f)
    except Exception as e:
        if not quiet:
            print(e)
        return None
        
def dump_data(data, filepath, quiet=False):
    save_error = None
    try:
        with open(filepath, mode='wb') as f:
            pickle.dump(data, f)
    except Exception as e:
        save_error = e
    if not quiet:
        if save_error:
            print(save_error)
        else:
            print('saved', filepath)
    
        
if __name__ == '__main__':

    file_freq  = './result/result_patterns-125-freq.pkl'
    # file_stdev = './result/result_patterns-125-std.pkl'

    ranked_terms = {
        #     "stdev55-m10!" : file_stdev,
        #     "stdev55" : 'result_patterns-125-stdev-55parts.pkl',
        #     "stdev35" : 'result_patterns-125-stdev-35parts.pkl',
        #     "stdev25" : 'result_patterns-125-stdev-25parts.pkl',
        #     "stdev20" : 'result_patterns-125-stdev-20parts.pkl',
        #     "stdev17" : 'result_patterns-125-stdev-17parts.pkl',
        #     "stdev15" : 'result_patterns-125-stdev-15parts.pkl',
        #     "stdev70" : 'result_patterns-125-stdev-70parts.pkl',
        #     "stdev93" : 'result_patterns-125-stdev-93parts.pkl',
        #     "std112-m4" : 'result/patterns-125-min4-stdev-112parts.pkl',
        #     "std112-m6" : 'result/patterns-125-min6-stdev-112parts.pkl',
        #     "std112-m8" : 'result/patterns-125-min8-stdev-112parts.pkl',
        #     "std112-m10" : 'result/patterns-125-min10-stdev-112parts.pkl',
        #     "std187-m10" : 'result/patterns-125-min10-stdev-187parts.pkl',
        #     "std-t-55-m8" : 'result/patterns-125-min8-stdev-t-55parts.pkl',
        #     "std-55-m10" : 'result/patterns-125-min10-stdev-55parts.pkl',
        #     "std-55-m6" : 'result/patterns-125-min6-stdev-55parts.pkl',
        #     "std-55-m4" : 'result/patterns-125-min4-stdev-55parts.pkl',
        #     "std-55-m2" : 'result/patterns-125-min2-stdev-55parts.pkl',
        #     "std-55-m1" : 'result/patterns-125-min1-stdev-55parts.pkl',
        #     "std-t-134-m10" : 'result/patterns-125-min10-stdev-t-134parts.pkl',
            "std-t-90-m8" : 'result/patterns-125-min8-stdev-t-90parts.pkl',
        #     "std-t-68-m8" : 'result/patterns-125-min8-stdev-t-68parts.pkl',
            # "std-tn-68-m8" : 'result/patterns-125-min8-stdev-tn-68parts.pkl',
            # "std-tn-st-68-m8" : 'result/patterns-125-min8-stdev-tn-newstops-68parts.pkl',
            "def-ptt-m2" : 'result/patterns-162-min2-def-ptt.pkl',

            "freq" : file_freq,
        }

    for name in ranked_terms:
        fpath = ranked_terms[name]
        ranked_terms[name] = load_data(fpath)
        
    # Загрузка "эталонных" терминов из файла
    # ! слова в составных терминах (словосочетаниях) разделены "::"
    word_colloc_sep = "::"
    experts_terms_file = "../texts/" + "it_concept_list.txt"

    with open(experts_terms_file,'r') as file:
        words = file.read().split()
    #         loaded_corpus_word_groups.append( line.split(" ") )
    singleword_expert_terms = {w for w in words if word_colloc_sep not in w}
    multiword_expert_terms = {tuple(w.split(word_colloc_sep)) for w in words if word_colloc_sep in w}

    expert_terms = list(singleword_expert_terms) + list(multiword_expert_terms)

    print(len(expert_terms), 'expert_terms')
    

    names = ranked_terms.keys() # ["freq","stdev"]
    print(names)
    eval_data_list = [make_eval_data(
            [w for w,sc in ranked_terms[nm]],
            expert_terms,
            nm
        ) for nm in names]
        
    ev = Evaluator()
    
    ks1 = [1,2,3,5,10,25,20,30,40,50,75,100,125]
    # list(range(1,125+1))
    
    stats_dict = ev.ap_at_ks(ks1, eval_data_list)
    
    print('\n'+(' '*3), *(stats_dict[1].keys()), sep='\t')
    for k in stats_dict.keys():
        # for k in stats_dict[k].keys():
        vals = stats_dict[k].values()
        vals = map(lambda f:'%9f'%f, vals)
        print('%3d'%k, *(vals), sep='\t')
    
    stats_dict = ev.map_at_ks(ks1, eval_data_list*2)
    
    print('\n',stats_dict)
    
    f1_stats_dict = ev.f1_at_k(20, eval_data_list*2)
    
    print('\n',"f1_stats_dict:")
    print('\n',f1_stats_dict)
    
    recall_stats_dict = ev.mean_recall_at_k(20, eval_data_list*2)
    
    print('\n',"recall_stats_dict:")
    print('\n',recall_stats_dict)
