# coding=utf-8

import itertools
import math
import re
import pandas as pd

from extract_terms import ExtractTerms


text_sep_re = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ])|(?<=\n)\s+(?=[A-ZА-ЯЁ](?![A-ZА-ЯЁ]))")
    # (?=<[.!?]|\n|)
def extract_sentences_from_text(text):
    return text_sep_re.split(text)


class Position:
    word = 0       # сквозная нумерация слов текста
    sentence = 0   # сквозная нумерация предложений текста
    
    def __init__(self, word=0, sentence=0):
        self.word = word
        self.sentence = sentence


sentence_word_re = re.compile(r"(?:[А-ЯЁа-яёA-Za-z](?:[-`']\w+)*)+", flags=re.UNICODE)

class Sentence:
    
    def __init__(self, line, pos):
        self.line = line
        self.word_list = None
        self.words_positions = None
        self.beginpos = pos
        self._parse_line()
        # set `end` pos
        self.endpos = Position(pos.word + self.size()-1, pos.sentence)
        self.lemmas_positions = None
   
    def _parse_line(self):
        self.word_list = [w.lower() for w in sentence_word_re.findall(self.line) if len(w)>0]
        # "перенумеровать" слова позициями
        self.words_positions = {}
        for i in range(len(self.word_list)):
            w = self.word_list[i]
            if w not in self.words_positions:
                self.words_positions[w] = [ i ]
            else:
                self.words_positions[w] += [ i ]

    def lemmatize_words(self, lemmatizer):
        """find lemmas for all words in the sentence"""
        assert lemmatizer and hasattr(lemmatizer, '__call__')
        assert self.words_positions
        
        # "перенумеровать" леммы позициями
        self.lemmas_positions = {}
        for w in self.words_positions:
            indices = self.words_positions[w]
            lemmas = lemmatizer(w)
            for lemma in lemmas:
                if lemma not in self.lemmas_positions:
                    self.lemmas_positions[lemma] = indices
                else:
                    self.lemmas_positions[lemma] += indices

    def __len__(self):
        """ Количество слов в предложении """
        return len(self.word_list)
        
    def size(self):
        """ Количество слов в предложении """
        return len(self.word_list)
        
    def count_of(self, word):
        """ Возвращает количество вхождений поданного слова. Универсальная функция,
            принимает сложные структуры (set, list, tuple), которые рекурсивно раскрываются и
            должны заканчиваться либо строкой, либо термином (Term). """
        if hasattr(word, 'lemmas'):
            # a term passed
            return self.count_of_term(word)
        if type(word) is str:
            for d in (self.lemmas_positions, self.words_positions):
                if word in d:
                    return len(d[word])
            return 0
        # ckeck if word is array-like containing strings
            # if bool(word) and isinstance(word[0], str) and not isinstance(word, str):
        if type(word) in (set, list, tuple):
            return sum([self.count_of(w)  for w in word]) # resurse with each word
        else: # word is of unknown type
            print('Warning: word is of unknown type:', type(word))
            return 0

    def match_term(self, term):
        """ Возвращает список кортежей с цепочками слов, совпавших с поданным термином. """
        ps = self.positions_of_term(term)
        n = len(term.words) # длина фразы [1..*)
        return [tuple(self.word_list[p:p+n]) for p in ps]
        
    def count_of_term(self, term):
        """ Возвращает количество цепочек слов, совпавших с поданным термином. """
        return len(self.positions_of_term(term))
        
    def positions_of_term(self, term):
        """ Возвращает список позиций цепочек слов, совпавших с поданным термином. """
        assert self.words_positions
        assert self.lemmas_positions is not None
        assert term.words
        assert term.normalized
        assert term.lemmas
        
        # найти совпадения со всеми словами термина ...
        n = len(term.words) # длина фразы [1..*)
        t_norms = term.normalized.split()
        # все формы слова в соответстие позиции во фразе
        t_forms = [{t_norms[i], str(term.words[i]), *(term.lemmas[i])} for i in range(n)]
        
        positions = None # позиции (в предложении) слов фразы
        for i in range(n):
            indices = set() # позиции текущего слова фразы
            for w in t_forms[i]:
                for d in (self.lemmas_positions, self.words_positions):
                    if w in d:
                        indices.update( d[w] )
            if positions is None:
                positions = indices  # для первого слова
            else:  # для 2-го и далее слов
                positions = {p+1 for p in positions} # инкрементируем индексы предыдущего слова для совпадения с текущим
                positions.intersection_update(indices)
                if not positions: # пересечение пусто
                    return []
                
        if not positions: # пересечение пусто
            return []
#         return position) # кол-во "доживших индексов"
        return sorted([p-n+1 for p in positions]) # список индексов первых слов совпадений со словами предложения


class Chapter(object):
    """ Глава """

    def __init__(self, title='NoTitle', text=None, sentences=None, extract_terms_instance=None):
        self.sentence_list = sentences or []
        
        # поля для открытого использования
        self.title = title
        self.user_data = None  # (для хранения связаных данных)
        self.text = None
        
        if text and type(text) is str:
            self.load_text(text)
        
        self.__time_weights_cache = None
        self.__extract_terms = extract_terms_instance or None
        self.__lemmatize = None
        self.__vocabulary_cache = None
        self.__term_candidates_cache = None
    
    def clear_cache(self):
        " reset cached data if any "
        self.__time_weights_cache = None
        self.__vocabulary_cache = None
        self.__term_candidates_cache = None
    
    def get_morph(self):
        """ returns pymorphy2 parser instance or None"""
        if self.__extract_terms:
            return self.__extract_terms.morph
        else:
            return None
        
    def get_extract_terms(self):
        """ returns ExtractTerms instance or None"""
        return self.__extract_terms
        
    def load_text(self, txt, start_position=None):
        assert txt and type(txt) is str
        self.text = txt
        sentence_lines = extract_sentences_from_text(txt)
        # make_chapter_from_sentences ...
        current_pos = start_position or Position()
        self.sentence_list.clear()

        for line in sentence_lines:
            snt = Sentence(line, current_pos)

            current_pos = snt.endpos
            current_pos.word += 1
            current_pos.sentence += 1

            self.add_sentence( snt )
        
    def add_sentence(self, sentence):
        """ Добавить предложение (типа Sentence) в конец Главы """
        if sentence.size() <= 0:
            return
        self.sentence_list.append(sentence)
        self.beginpos = self.sentence_list[0].beginpos
        self.endpos = self.sentence_list[-1].endpos
        # reset cached weights if any
        self.clear_cache()
        
    def get_term_candidates(self, limit=None):
        """return term candidates list optionally cropped with limit """
        assert self.__term_candidates_cache, "Run Chapter.prepare_terms() first!"
        return self.__term_candidates_cache[:limit]
        
    def find_terms(self, substr, limit=None, exact_match=False):
        """ получить термы по полному совпадению или по части слова """
        assert limit is None or limit > 0
        found = []
        for t in self.get_term_candidates():
            if substr == t.normalized  if exact_match else  substr in t.normalized:
                found.append(t)
                if limit and len(found) >= limit:
                    break
        return found

    def term_stdev_rank(self, term, parts):
        """
        Получить вес термина как среднеквадратическое отклонение его профиля, сжатого до `parts` фрагментов.
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
        t_series = self.compress_profile(parts, self.profile4word_or_family(term) )
        rank = t_series.std() * len(t.words)  # повышаем вес многословных терминов
        del t_series
        return rank

    def get_stopwords(self):
        """return set of stopwords"""
        assert self.__extract_terms
        return self.__extract_terms.stopwords
        
    def prepare_terms(self, stopwords_file=None, quiet=False):
        """Init term candidates and sentences for getting profiles"""
        self.prepare_term_candidates(stopwords_file=stopwords_file, quiet=quiet)
        self.lemmatize_sentences()
        
    def prepare_term_candidates(self, stopwords_file=None, quiet=False):
        """Extract nominal groups from the text"""
        assert self.text
        self.__extract_terms = self.__extract_terms or ExtractTerms(
                stopwords_file=stopwords_file or ('text-corpus/stopwords.txt')
            )
        self.__term_candidates_cache = self.__extract_terms(self.text, quiet=quiet)
        assert self.__term_candidates_cache, "No significant words it text... (All the words seem to be removed as stopwords)"
        
    def lemmatize_sentences(self):
        """Make a vocabulary from the text"""
        assert self.__extract_terms
        assert self.__term_candidates_cache
        self.__lemmatize = self.__lemmatize or self.__extract_terms.get_lemmatizer(self.__term_candidates_cache)
        
        # пройти по всем предложениям и лемматизировать все слова в них
        for sentence in self.sentence_list:
            sentence.lemmatize_words(lemmatizer=self.__lemmatize)
            
            
    def run_on_text(self, txt, sentences_per_part_list=None, parts_list=None, min_count=1, limit=None):
        """
        run_on_text(self, txt, sentences_per_part_list=None, parts_list=None, min_count=1, limit=None)
        -> None или dict:
            {
            'freq'  : [ ('word',score), ...],
            'stdev-[1T]': [ ('word',score), ...],
            'stdev-[2T]': [ ('word',score), ...],
             ...
            'stdev-[NT]': [ ('word',score), ...],
           }
            
            где в [nT] (квадратные скобки не ставятся):
                n - каждое число из `parts_list` или `sentences_per_part_list`,
                T - один символ - тип числа n (как подано на вход):
                    's' - sentences per part
                    'p' - total parts
            Внимание.
                Из указанных делений на parts могут быть взяты не все, если при таком делении фрагментов в тексте окажется меньше 2.
                Если все варианты не подойдут, то вместо пустого списка вернётся None.

        txt (str):
            текст для обработки
        sentences_per_part_list - list(int) или int:
            сжимать до фрагментов так, чтобы они содержали указанное число предложений
        parts_list - list(int) или int:
            получить варианты стандартного отклонения для профилей слов, сжатых до указанных размеров
            Этот параметр игнорируется, если задан `sentences_per_part_list`.
        limit (int):
            ограничить длину каждого выходного ранжированного списка терминов.
        min_count (int):
            не рассматривать кандидатов в термины, которые употребляются реже, чем min_count.
            
        """
        assert txt and len(txt) > 100
        assert min_count > 0
        assert limit is None or limit > 0
        assert sentences_per_part_list or parts_list
        
        # загружаем текст, чтобы уже иметь кол-во предложений в нём
        self.load_text(txt)
        
        def s_per_part2parts(self, s_per_part):
            return len(self) // s_per_part
            
        parts_and_suffices = []
            
        
        if sentences_per_part_list:
            # преобразовать sentences_per_part_list в parts_list ...
            sentences_per_part_list = ([sentences_per_part_list]  if (type(sentences_per_part_list) is int) else  sentences_per_part_list)
            assert all([s_per_part > 0 for s_per_part in sentences_per_part_list])
            
            parts_and_suffices = [
                    (s_per_part2parts(self,s_per_part), '-%ds' % s_per_part)
                    for s_per_part in sentences_per_part_list
                ]
        else:
            parts_list = [parts_list]  if (type(parts_list) == int) else  parts_list
            parts_and_suffices = [
                    (parts, '-%dp' % parts)
                    for parts in parts_list
                ]
        
        assert all([parts > 0 for parts,_suffix in parts_and_suffices])
        

        MIN_PARTS = 2

        
        # Убрать из списка те, которые имеют  parts < MIN_PARTS
        parts_and_suffices = list(filter(lambda p:p[0] >= MIN_PARTS, parts_and_suffices))
        
        if not parts_and_suffices:
            return None # !!!  поданы неподходящие этому тексту параметры (слишком короткий текст)
        
        res_dict = dict()
        self.prepare_terms()
        
        print('freq', end=' ...\t')
        freq_terms = [(t.normalized, t.count) 
                      for t in self.get_term_candidates() 
                      if t.count >= min_count]
        
        freq_terms = freq_terms[:limit]
        freq_terms.sort(key=lambda e:-e[1])
        
        # save
        res_dict['freq'] = freq_terms

        for parts,suffix in parts_and_suffices:
            print('stdev'+suffix, '(%dp)' % parts, end='...  ')
            std_ranked = [( t.normalized, self.term_stdev_rank(t, parts) )
                          for t in self.get_term_candidates() 
                          if t.count >= min_count]

            std_ranked = std_ranked[:limit]
            std_ranked.sort(key=lambda e:-e[1]) 

            # save
            res_dict['stdev'+suffix] = std_ranked
        
        print('run done.')
        return res_dict
        
        
    def __len__(self):
        return self.size()

    def size(self):
        return len(self.sentence_list)
        
    def word_count(self):
        return sum([s.size() for s in self.sentence_list])
        
    def count_of(self, word):
        return sum([s.count_of(word) for s in self.sentence_list])
        # ckecks if word is an array
        
    def raw_profile(self, word):
        "returns list[float]"
        return [s.count_of(word) for s in self.sentence_list]
        
    def raw_weights(self):
        "returns list[float]"
        return [s.size() for s in self.sentence_list]

    def timeSeries_weights(self):
        "returns Series[Timedelta]"
        if self.__time_weights_cache is None:
            self.__time_weights_cache = self._weights2time_index(self.raw_weights())
        return self.__time_weights_cache

    def _weights2time_index(self, profile_weights):
        """
        convert weights into a time series.
        A weight is just a length of a sentence.
        Assume that one word equals to one second of time.
        """
        start_ts = pd.Timedelta(seconds=0)  # pd.Timestamp(2000, 1, 1)
        current_ts = start_ts + pd.Timedelta(seconds=0)

        def next_ts(span):
            nonlocal current_ts
            current_ts += pd.Timedelta(seconds=span)
            return current_ts

        return pd.Series(map(next_ts, profile_weights))

        
    def profile4word_or_family(self, word):  ### , size
        "returns Series[Timedelta -> int]"
        raw_profile = self.raw_profile(word)
        weights_index = self.timeSeries_weights()
        # Get name from Family instance or first word from array
        name = ( # isinstance(word, Family) and word.lemma  or
                hasattr(word, 'normalized') and word.normalized
                or  bool(word) and type(word) in (set, list, tuple) and str(next(iter(word)))
                or  'no-name'
                )
        word_series = pd.Series(raw_profile, index=weights_index, name=name)
        return word_series
        # return self.compress_profile(size, raw_profile,
                                     # self.raw_weights())

    def resample_interval(self, parts):
        "returns formatted string like '1000s'"
        # interval = '30T' # 30 мин
        # interval = '1000s' # 1000 сек
        weights_index = self.timeSeries_weights()
        text_duration = weights_index.iat[-1].seconds  # get seconds of last index (top of Timedelta range [0..duration])
        sec_span = math.ceil(text_duration / parts)
        return str(sec_span)+'s'

    def compress_profile(self, parts, word_series):
        """returns pd.Series with index of 'Timedelta's
        assuming that:   size < word_series.size"""
        
        interval = self.resample_interval(parts)
        return word_series.resample(interval).sum()

    # собираем сжатые профили в один DataFrame
    def profiles4families(self, parts, family_list):
        """family_list should contain true <class Family> objects with not-empty `lemma` fields.
        returns a DataFrame with compressed profiles for all families."""
        df = pd.DataFrame()
        for family in reversed(family_list):
            s = self.profile4word_or_family(family)
            s = self.compress_profile(parts, s)
            ## already done ## s.name = family.lemma or family.words[0]
            # print(s.name)
            #  insert before 0th column one more column with data  (mutable operation)
            df.insert(0, s.name, s)
        return df

    # находим корреляции целиковых профилей для семейств
    def corr4families(self, parts, family_list, corr_treshold=0.6):
        """returns correlation matrix for family pairs whose correlation is above `corr_treshold`
        Usage of returned DataFrame:
        # get single value: tuple of correlated words pair: ('тип', 'метод'), parts count: 40
        stat_df.at[('тип', 'метод'), 40 ]
        # get by explicit key: returns Series of corr values indexed by `parts` value (possibly with NaNs):
        stat_df.xs( ('тип', 'метод') )
        # slice by range/set of keys: returns DataFrame:
        pd.DataFrame(stat_df, columns=stat_df.columns[:20])"""
        
        df = self.profiles4families(parts, family_list)
        print('got profiles for', parts, 'parts.')
        
        df = prepare_df4corr(df, treshold4part=4, treshold4text=20) ### ??? вычислять динамически?
        print('removed columns with leak of useful data')
        
        # посчитать корреляцию между профилями для отобранных слов
        corr_df = df.corr()
        print('got correlation matrix')
        
        # отсеять диагональные единицы
        corr_df = corr_df[corr_df<1]
        
        # corr_max = corr_df.max().max()
        # corr_min = corr_df.min().min()
        # # print(corr_max, corr_min) ### info
        
        # порог отсева по максимальной корреляции слова с другими в строке

        for i1 in corr_df.columns: # ["семейство"]['типам']
            if corr_df[i1].max() < corr_treshold:
                corr_df.drop(columns=i1, inplace=True)
                corr_df.drop(index=i1, inplace=True)
                print(i1,'\t','removed from correlation matrix (columns & rows)') ### info
            
        print('removed columns & rows of low-correlated words')

        # remove values below the corr_treshold
        corr_df = corr_df[corr_df>corr_treshold]
        
        return corr_df
        

def add_corr_stats4parts(parts, corr_df, stats_df):
    """Adds new row indexed with `parts` to `stats_df` and saves values from `corr_df` into it.
    returns new pd.DataFrame - modified `stats_df`."""

    idx_list = []
    val_list = []
    
    for word_pair in itertools.combinations(corr_df.index, 2):
        w1,w2 = word_pair
        idx_list.append(word_pair)
        val = corr_df.loc[w1].loc[w2]
        val_list.append(val)

    s = pd.Series(name=parts, data=val_list, index=idx_list).dropna()
    #     print(s)
    stats_df = stats_df.append(s)
        
    return stats_df



def zero_all_below_treshold(df, treshold):
    """
    Replaces with 0 all values that below treshold.
    returns new pd.DataFrame
    """
    # заменим нулями все значения, меньшие порогового
    return df[df >= treshold].fillna(0)


def prepare_df4corr(dataframe, treshold4part, treshold4text):
    """
    Lowers down to zero small values below treshold4part.
    Drops out columns for words with total count below treshold4text.
    returns new pd.DataFrame
    """
    df = zero_all_below_treshold(dataframe, treshold4part)
    
    for i1 in df.columns: # ["семейство"]['типам']
        if df[i1].sum() < treshold4text:
            print(i1, '\t','removed from columns') ### info
            df.drop(columns=i1, inplace=True)

    return df


def should_exclude(word):
#! uses outer variable `stopwords`
    wlen = len(word)
    for stopw in stopwords:
        if abs(len(stopw) - wlen) > 2:
            continue
        if distance_between(word, stopw) < 0.7:
            print(word, '\t', end='')
            return True
    return False

def create_filtered_vocabulary(iterable_words, min_word_length=3):
    " Получить словарь уникальных слов загруженного корпуса "
    # 
    print(len(iterable_words),'total words')
    
    new_vocabulary = set()
    for w in iterable_words:
        if  w[0].isdigit()  or  w in stopwords  or  len(w)<min_word_length:
            continue
        new_vocabulary.add(w)
    #
    print(len(new_vocabulary),'unique words in pre-filtered vocabulary')

    print('excluded words:\t', end='')
    for w in set(new_vocabulary):
        if should_exclude(w):
            new_vocabulary.remove(w)
    #
    print("\n",len(new_vocabulary),'unique words in filtered vocabulary')
            
    return new_vocabulary

            
# # создать и отфильтровать словарь корпуса
# corpus_vocabulary = create_filtered_vocabulary([w for s in main_chapter.sentence_list for w in s.word_list])
    


if __name__ == '__main__':
	# пример разбора
	# _t = """Погружение в 
	# ПАТТЕРНЫ 
	# ПРОЕКТИРОВАНИЯ 
	# v2018-1.5 
	# Вместо копирайта 
	# Привет! Меня зовут Александр Швец, я автор  книги Погружения в Паттерны, а также  онлайн курса Погружение в Рефакторинг. 
	# АБСТРАКТНАЯ  ФАБРИКА
	# Эта книга предназначена для вашего личного  пользования. Пожалуйста, не передавайте  книгу третьим лицам, за исключением членов  своей семьи. Если вы хотите поделиться книгой с друзьями  или коллегами, то купите и подарите им легальную копию  книги. 
	# """

	# ss = extract_sentences_from_text(_t)
	# print(len(ss))
	# print('<|>\n'.join(ss))

    # import os
    # print(os.getcwd())
    
    with open('../texts/patterns.txt', "r", newline="", encoding='utf-8') as file:
        txt = file.read()
        
    # shrink text
    txt = txt[:55000]
    
    test_sentence = """
    Вообще-то, не всякий Фабричный метод всякому фабричному методу рознь!
    А кто более того интерфейса с паттерном "фасадом" ... 
    Хорошими Фабричными методами не всякий похвастаться может!
    """
    
    main_chapter = Chapter()

    stats = main_chapter.run_on_text(test_sentence + txt, sentences_per_part_list=list(range(10,70+1,20)), limit=200)
    print(stats.keys())
    print(next(iter(stats.items())))
    
    print(len(main_chapter), 'sentences')
    


    # main_chapter.prepare_terms()
    
    # terms2 = main_chapter.get_term_candidates()
    # print(len(terms2), 'term candidates')
    
    # print('>>>> terms which norm is not in lemma:')
    # i = 0
    # for t in terms2:
        # if len(t.words) == 1 and t.normalized not in t.lemmas[0]:
            # i += 1
            # print(i, ")", t.normalized, ':\t', t.count, '\t', t.lemmas)
    # print('<<<<<<<<<<')

    # print(list(map(main_chapter._Chapter__lemmatize, ['велики', 'автомобилей', 'предметам'])))
    
    # term1 = None
    # phrase2 = None
    
    # for t in terms2:
        # if 'паттерн' in t.normalized:
            # term1 = t
        # if len(t.words) >= 2:
            # if not phrase2:
                # phrase2 = t
            # print(t.normalized, ':\t', t.count, '\t', t.lemmas)
            # break
            
    # print(term1.normalized, '\tchosen!')
    # print(phrase2.normalized, '\tchosen!')
        
    # for s in main_chapter.sentence_list[:22]:
        # print(s.word_list)
        # print(s.count_of(term1), '/', s.count_of(phrase2))

        