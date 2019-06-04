# coding=utf-8

import math

from rutermextract import TermExtractor
import rutermextract
import pymorphy2

STOPWORDS_FILE = '../texts/' + 'stopwords.txt'


class ExtractTerms(object):
    """
    Извлечение ключевых слов из текста c дополнительными фильтрацией и объединением кандидатов.
    """

    def __init__(self, stopwords_file=None, stopwords=None):
        # stopwords_file [string] - path to file containing stopwords
        assert stopwords_file or stopwords
        
        stopwords_file = stopwords_file or STOPWORDS_FILE
        self.stopwords = stopwords or load_wordset(stopwords_file)
        self.term_extractor = TermExtractor()
        self.morph = self.term_extractor.parser.morph
        self._morph_parse_cache = {}
        
    def __call__(self, text, limit=None, weight=None, strings=False, nested=False, quiet=False):
        # call rutermextract
        terms = self.term_extractor(text, limit=limit*2 if limit else limit,
                                    weight=weight, strings=False, nested=nested)

        ###
        terms_out = len(terms) # print('before stopwords filtering:',len(terms))
        ###

        self.filter_by_stopwords(terms)

        ###
        terms_out -= len(terms) # print('after  stopwords filtering:',len(terms))
        if not quiet and terms_out > 0:
            print('Removed %d terms matched the stopwords.' % terms_out)

        terms_out += len(terms)
        ###

        joined_terms = self.join_terms(terms)

        ###
        terms_out -= len(joined_terms)
        if not quiet and terms_out > 0:
            print('%d total terms removed while joining & filtering.' % terms_out)
        ###

        # сортировать!
        joined_terms.sort(key=lambda t:-t.count)

        result = joined_terms[:limit]
        if strings:
            return [term.normalized for term in result]
        else:
            return result

    def filter_by_stopwords(self, terms):
        if not self.stopwords:
            return terms
            
        words_to_remove_cache = set()

        for t in terms[:]: # make shallow copy to avoid deletion bugs
            should_remove = False
            t_words = set( t.normalized.split() + [str(word) for word in t.words] )
            if t_words.intersection(words_to_remove_cache): # not empty
                should_remove = True
            elif t_words.intersection(self.stopwords): # not empty
                should_remove = True
            else:
                # гипотезы морфологического разбора
                for word in t_words:
                    hyps = self.morph.parse(word)
                    # множество лемм-гипотез
                    lemmas_set = {p.normal_form for p in hyps}
                    common_stops = lemmas_set.intersection(self.stopwords)
                    if common_stops: # not empty
                        words_to_remove_cache.add(word)
                        words_to_remove_cache.update(lemmas_set)
                        should_remove = True
                        break

            if should_remove:
                # убираем неподходящего кандидата из списка
                # # print('mathes stopword :', t.normalized, '; set:', t_words)
                terms.remove( t )

        words_to_remove_cache.clear()
        return terms

    def join_terms(self, terms):
        "-> joined (by case, multiplicity, ...) and filtered terms list"

        def lemma_pattern(term):
            "tuple of sets(each set of lemmas) , dict(lemma -> score for term)"

            def score4term(term, morph_tag):
                # не-слово: -1, если [лат.буквы, пунктуация, число, не разобрано] иначе 1
                if any([gram in morph_tag for gram in {'LATN', 'PNCT', 'NUMB', "UNKN"}]):
                    return -1

                # часть речи: 1, если [сущ., полн. прил., полн. прич.] иначе 0
                k_POS = int(morph_tag.POS in ('NOUN','ADJF','PRTF'))
                # число: ед.
                k_number = 5 if morph_tag.number == 'sing' else 1
                # неодушевлëнность
                k_inan = 5 if morph_tag.animacy == 'inan' else 0.75
                # падеж: им.
                k_case = 2 if morph_tag.case == 'nomn' else 1
                return math.log1p(term.count) * k_POS * k_number * k_inan * k_case

            # гипотезы морфологического разбора
            hyps = [self.morph_parse(str(word)) for word in term.words]
            # кортеж из множеств лемм-гипотез
            lemmas_tuple = tuple([set([p.normal_form for p in hyp]) for hyp in hyps])
            # добавить варианты разбора для итоговых лемм (чтобы ранжировалось не только по частным формам слов)
            analyzed_word_forms = {p.word for hyp in hyps for p in hyp}
            analyzed_lemmas = {p.normal_form for hyp in hyps for p in hyp}
            for word in term.normalized.split():
                if word not in analyzed_word_forms:
                    lemma_hyps = self.morph_parse(word)
                    for hyp in lemma_hyps:
                        if hyp.normal_form in analyzed_lemmas: # не добавляем варианты разбора с леммами, отличными от уже найденных
                            hyps[-1].append(hyp)

            scores = dict() # словарь оценок
            for hyp in hyps:
                for p in hyp:
                    lemma = p.normal_form
                    score = score4term(term, p.tag)
                    # сохранить лучшую оценку для леммы
                    if lemma not in scores:
                        scores[lemma] = score
                    else:
                        scores[lemma] = max(scores[lemma], score)

            return lemmas_tuple, scores


        def are_patterns_match(ptt1, ptt2):
            # совпадают длины и для каждого есть совпадающие (общие) леммы
            return len(ptt1) == len(ptt2) and all([ptt1[i].intersection(ptt2[i]) for i in range(len(ptt1))])


        patterns = []
        joined = dict()
        
        fake_terms_out = 0

        for t in terms:
            lemmas_pattern, lemma_scores = lemma_pattern(t) # pattern for current t
            ptt_i = len(patterns)
            patterns.append(lemmas_pattern)

            what2add = (t, lemma_scores) # текущий терм с его оценками по леммам

            for p_i in joined:
                if are_patterns_match(patterns[ptt_i],patterns[p_i]):
                    joined[p_i].append(what2add) # добавить в объединение новый терм
                    break
            else: # no break
                joined[ptt_i] = [what2add] # создать новое объединение из текущего терма

        #     итоговый список
        judged_terms = list()

        for ptt_i in joined:
            ptt = patterns[ptt_i]
            joined_terms = joined[ptt_i]
            if len(joined_terms) == 1:  # других форм этого термина не найдено не найдено
                base_term = joined_terms[0][0] # 1st of list & 1st of tuple
                lemma_scores = joined_terms[0][1] # 1st of list & 2nd of tuple
                # исключить, если в составе есть неразбираемые "слова":
                #  all-все слова фразы, any - хотя бы одно
                if any([score<0 for score in lemma_scores.values()]):
                    ### print('Skip fake term:\t',base_term.normalized, '.')
                    fake_terms_out += 1
                    continue
                # дописать lemmas_pattern
                base_term.lemmas = ptt
                judged_terms.append(base_term)
            else:
                # находим все леммы, общие для всех терминов в объединении (слив леммы фраз воедино)
                ptt_intersection = {word for group in ptt for word in group}  # flatten set of lemmas
                for t,t_lemma_scores in joined_terms[:]:
                    t_lemmas = set(t_lemma_scores.keys())
                    temp_intersection = ptt_intersection.intersection(t_lemmas)

                    if not temp_intersection:  # если текущий термин создал пустое пересечение
#                         print('Can`t join (to',ptt_intersection,'): ',end='\t')
                        # убираем неподходящего кандидата из списка
                        joined_terms.remove( (t,t_lemma_scores) )
                        # добавляем этот терм отдельно
                        t.lemmas = ({t.normalized},) # правильную лемму мы не знаем, поэтому - само слово
                        judged_terms.append( t )
#                         print(t.normalized,end='')
#                         print('.')
                        continue

                    ptt_intersection = temp_intersection

                if not ptt_intersection:  # если пустое пересечение
                    # добавляем все термы по отдельности
#                     print('Can`t join (no common lemmas): ',end='\t')
                    for t,t_lemma_scores in joined_terms:
                        t.lemmas = ({t.normalized},) # правильную лемму мы не знаем, поэтому - само слово
                        judged_terms.append( t )
#                         print(t.normalized,end=' , ')
#                     print('.')
                    continue

                # по очкам общих лемм ранжируем все термины в объединении
                t_ranks = [] # рейтинг терминов по порядку
                for t,t_lemma_scores in joined_terms:
                    # просуммировать очки текущего термина по общим леммам
                    rank = sum([t_lemma_scores[lemma] for lemma in ptt_intersection])
                    t_ranks.append(rank)

                    ###
                    # if 'цвет' in str(ptt_intersection):
                        # print('rank for',ptt_intersection,':', t.normalized, '(',list(map(str,t.words)),')')
                        # print('t_lemma_scores:',t_lemma_scores)
    # #                     print({joined_terms[i][0].normalized: t_ranks[i] for i in range(len(joined_terms))})

                # find index of max rank
                max_rank_i = t_ranks.index(max(t_ranks))

                if t_ranks[max_rank_i] <= 0:  # если максимальные очки ушли в 0
                    # добавляем все термы по отдельности
#                     print('Can`t join (zero max rank): ',end='\t')
                    for t,t_lemma_scores in joined_terms:
                        t.lemmas = ({t.normalized},) # правильную лемму мы не знаем, поэтому - само слово
                        judged_terms.append( t )
#                         print(t.normalized,end=' , ')
#                     print('.')
                    continue

                # формируем лучший термин
                base_term = copyTerm(joined_terms[max_rank_i][0])
                # дописать lemmas_pattern
                base_term.lemmas = ptt
                sum_count = sum([t[0].count for t in joined_terms])
                base_term.count = sum_count
                # if len(joined_terms) > 1:
                    # add other norm forms for reference to the choice made
                    # # base_term.alt_normalized = [(t.normalized, t.count) for t,_ in joined_terms  if t!=base_term]
                    # # base_term.alt_words = [t.words for t,_ in joined_terms  if t!=base_term]
                judged_terms.append( base_term )


        #     def _join_old(joined_terms):
        #         if len(joined_terms) == 1:
        #             return joined_terms[0]
        #         else:
        #             max_count = max([t.count for t in joined_terms])
        #             sum_count = sum([t.count for t in joined_terms])
        #             base_term = copyTerm([t for t in joined_terms  if t.count==max_count][0])
        #             base_term.count = sum_count
        #             # add other norm forms
        #             base_term.alt_normalized = [(t.normalized, t.count) for t in joined_terms  if t!=base_term]
        #             return base_term

        patterns.clear()
        joined.clear()
        if fake_terms_out > 0:
            print('Removed %d fake (non-russian) terms.' % fake_terms_out)
        return judged_terms

    def get_lemmatizer(self, extracted_terms):
        return Lemmatizer(self.morph, extracted_terms, self._morph_parse_cache)

    def morph_parse(self, word):
        if word in self._morph_parse_cache:
            return self._morph_parse_cache[word]
        
        hyps = self.morph.parse(word)
        # update cache
        self._morph_parse_cache[word] = hyps
        return hyps
            
        
    def clear_cahe(self):
        self._morph_parse_cache.clear()

    


class Lemmatizer(object):
    """ Лемматизатор с опциональным словарём допустимых лемм """
    
    def __init__(self, morph, terms_list=None, morph_parse_cache=None):
        """ Инициализировать Лемматизатор
            terms_list - список объектов-терминов, содержащих поле `lemmas` с леммами (каждый)
            morph - экземпляр морфолог. анализаторалл (pymorphy2.Morph) 
            morph_parse_cache - словарь (dict), содержащий кеш запросов к pymorphy2.Morph.parse(). Если задан, то будет использоваться и обновляться, если нет - то не будет создан.
        """
        self.morph = morph
        self._morph_parse_cache = morph_parse_cache
        self.lemmas = None
        if terms_list:
            self.set_lemmas_from_terms(terms_list)

    def set_lemmas_from_terms(self, terms_list):
        self.lemmas = {w for t in terms_list for lemma_list in t.lemmas for w in lemma_list}

    def lemmatize_word(self, word):
        """ Выполнить лемматизацию слова и вернуть список лемм.
            Если предварительно задан перечень допустимых лемм, то останутся только
            допустимые леммы.
        returns: set(str) - множество лемм слова в виде строк """
        
        # гипотезы морфологического разбора
        hyps = self.morph_parse(str(word))
        # множество лемм-гипотез
        lemmas_set = {p.normal_form for p in hyps}
        return lemmas_set.intersection(self.lemmas)  if self.lemmas else  lemmas_set

    def __call__(self, word):
        return self.lemmatize_word(word)

    def morph_parse(self, word):
        
        if self._morph_parse_cache and word in self._morph_parse_cache:
            return self._morph_parse_cache[word]
        
        hyps = self.morph.parse(word)
        if self._morph_parse_cache:
            # update cache
            self._morph_parse_cache[word] = hyps
            return hyps
    


def load_wordset(stops_file):
    " Загрузить список слов, например стоп-слова "
    try:
        with open(stops_file,'r', encoding='utf-8') as file:
            words = file.read().split();
        return set(words);
    except:
        print('Warning: cannot load words from file:', stops_file)
        return None


def copyTerm(objTerm):
    "Construct new instance of rutermextract.term_extractor.Term"
    return rutermextract.term_extractor.Term(
        words=objTerm.words,
        normalized=objTerm.normalized,
        count=objTerm.count)

def makeTerm(words=[], normalized="", count=0):
    "Construct new instance of rutermextract.term_extractor.Term"
    return rutermextract.term_extractor.Term(
        words=words,
        normalized=normalized,
        count=count)

