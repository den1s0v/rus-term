import itertools
import math
import re
import pandas as pd

# import our class Family & more...
# from concepts.word_family import *

# from concepts.extract_terms import *?
from concepts.extract_terms import ExtractTerms


text_sep_re = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ])|(?<=\n)\s+(?=[A-ZА-ЯЁ](?![A-ZА-ЯЁ]))");
    # (?=<[.!?]|\n|)
def extract_sentences_from_text(text):
    return text_sep_re.split(text)


class Position:
    word = 0       # сквозная нумерация слов текста
    sentence = 0   # сквозная нумерация предложений текста
    
    def __init__(self, word=0, sentence=0):
        self.word = word
        self.sentence = sentence


# sentence_sep_re = re.compile(r"\W+")
sentence_word_re = re.compile(r"(?:[А-ЯЁа-яёA-Za-z](?:[-`']\w+)*)+");

class Sentence:
    line = ""
    # pos
    
    def __init__(self, line, pos):
        self.line = line
        self.beginpos = pos
        self.parse_line()
        # set `end` pos
        self.endpos = Position(pos.word + self.size()-1, pos.sentence)

   
    def parse_line(self):
        self.word_list = [w.lower() for w in sentence_word_re.findall(self.line) if len(w)>0]
        # "перенумеровать" слова позициями
        self.words_positions = {}
        for i in range(len(self.word_list)):
            w = self.word_list[i];
            if w not in self.words_positions:
                self.words_positions[w] = [ i ];
            else:
                self.words_positions[w] += [ i ];
            
#         print(self.word_list)
        
        
    def __len__(self):
        return len(self.word_list)
        
    def size(self):
        return len(self.word_list)
        
    def count_of(self, word):
        # ckeck if word is array-like containing strings
        if bool(word) and isinstance(word[0], str) and not isinstance(word, str):
            return sum([self.count_of(w)  for w in word]) # resurse with each word
        else: # word is a string
            return 0  if word not in self.words_positions else  len(self.words_positions[word]);

class Chapter:  # Глава

    def __init__(self):
        self.sentence_list = []   
        # self.__weights_cache = None
        self.__time_weights_cache = None
        
    def add_sentence(self, sentence):
        if sentence.size() <= 0:
            return
        self.sentence_list.append(sentence)
        self.beginpos = self.sentence_list[0].beginpos
        self.endpos = self.sentence_list[-1].endpos
        # reset cached weights if any
        self.__time_weights_cache = None
        
    def size(self):
        return len(self.sentence_list)
        
    def word_count(self):
        return sum([s.size() for s in self.sentence_list])
        
    def count_of(self, word):
        return sum([s.count_of(word) for s in self.sentence_list])
        # ckeck if word is an array
        
    def raw_profile(self, word):
        "returns list[float]"
        return [s.count_of(word) for s in self.sentence_list]
        
    def raw_weights(self):
        "returns list[float]"
        # if not self.__weights_cache:
        #     self.__weights_cache = [s.size() for s in self.sentence_list]
        # return self.__weights_cache
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
            return current_ts;

        return pd.Series(map(next_ts, profile_weights))

        
    def profile4word_or_family(self, word):  ### , size
        "returns Series[Timedelta -> int]"
        raw_profile = self.raw_profile(word)
        weights_index = self.timeSeries_weights()
        # Get name from Family instance or first word from array
        name = isinstance(word, Family) and word.lemma  or  bool(word) and word[0]  or  'no-name'
        word_series = pd.Series(raw_profile, index=weights_index, name=name)
        return word_series
        # return self.compress_profile(size, raw_profile,
                                     # self.raw_weights());

    def resample_interval(self, parts):
        "returns formatted string like '1000s'"
        # interval = '30T' # 30 мин
        # interval = '1000s' # 1000 сек
        weights_index = self.timeSeries_weights()
        text_duration = weights_index.iat[-1].seconds  # get seconds of last index (top of Timedelta range [0..duration])
        sec_span = math.ceil(text_duration / parts)
        return str(sec_span)+'s'

    def compress_profile(self, parts, word_series):
        "returns pd.Series with index of 'Timedelta's"
        "assuming that:   size < word_series.size"
        
        interval = self.resample_interval(parts)
        return word_series.resample(interval).sum()

    # собираем сжатые профили в один DataFrame
    def profiles4families(self, parts, family_list):
        "family_list should contain true <class Family> objects with not-empty `lemma` fields."
        "returns a DataFrame with compressed profiles for all families."
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
        "returns correlation matrix for family pairs whose correlation is above `corr_treshold`"
        "Usage of returned DataFrame:"
        "# get single value: tuple of correlated words pair: ('тип', 'метод'), parts count: 40"
        "stat_df.at[('тип', 'метод'), 40 ]"
        "# get by explicit key: returns Series of corr values indexed by `parts` value (possibly with NaNs):"
        "stat_df.xs( ('тип', 'метод') )"
        "# slice by range/set of keys: returns DataFrame:"
        "pd.DataFrame(stat_df, columns=stat_df.columns[:20])"
        
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
    "Adds new row indexed with `parts` to `stats_df` and saves values from `corr_df` into it."
    "returns new pd.DataFrame - modified `stats_df`."

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

def make_chapter_from_sentences(sentences):
    new_chapter = Chapter();

    # # nlines = 0;
    current_pos = Position()

    for line in sentence_lines:
    # #         nlines += 1
    # #         if(nlines >= 122):      # debug limit !
    # #             break
        snt = Sentence(line, current_pos)

        current_pos = snt.endpos
        current_pos.word += 1
        current_pos.sentence += 1

        new_chapter.add_sentence( snt );
    
    return new_chapter;


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




if __name__ == '__main__':
	# пример разбора
	_t = """Погружение в 


	ПАТТЕРНЫ 


	ПРОЕКТИРОВАНИЯ 


	v2018-1.5 


	Вместо копирайта 


	Привет! Меня зовут Александр Швец, я автор  книги Погружения в Паттерны, а также  онлайн курса Погружение в Рефакторинг. 
	АБСТРАКТНАЯ  ФАБРИКА

	Эта книга предназначена для вашего личного  пользования. Пожалуйста, не передавайте  книгу третьим лицам, за исключением членов  своей семьи. Если вы хотите поделиться книгой с друзьями  или коллегами, то купите и подарите им легальную копию  книги. 
	"""

	ss = extract_sentences_from_text(_t)
	print(len(ss))
	print('<|>\n'.join(ss))
