# Семейства слов, похожих по написанию

# https://pypi.org/project/python-Levenshtein/
from Levenshtein import distance as fast_Levenshtein_distance
import collections
import pymorphy2

# синглтон для анализатора (не нужно загружать, если не будем использовать)
pymorphy2_morph = None

def get_morph():
	global pymorphy2_morph
	if not pymorphy2_morph:
		pymorphy2_morph = pymorphy2.MorphAnalyzer() # загрузить анализатор
	return pymorphy2_morph


# расстояние между словами (параметры подбирались для руссского языка)
def distance_between(w1,w2):
	"consider no relation if the result is greater than 1"
	short, long = (w1,w2)  if (len(w1) < len(w2)) else  (w2,w1);
	len_short = len(short);
	len_long = len(long);
	
	# less that 3 chars OR diff more than 4 chars OR diff more than twice
	if (len_short < 3)  or  (len_long > 4 + len_short)  or  (len_long > 2 * len_short):
		return len_long; # the lengths are too different
	
	min_d = len_long;
	for i in range(len_long-len_short+1):
		min_d = min(min_d, fast_Levenshtein_distance(short, long[i:len_short+i]));
		# проверить для +-1 длин по длинному слову? для пропущенных букв
		if min_d == 0:
			break;
	
	return min_d / (min(8, len_short) / 3); ### min_d / (len_short / 3);
	

# Семейство слов
class Family:
	def __init__(self, words = [], lemma=None):
		self.lemma = lemma
		self.words = words
		
	def append(self, word):
		if(word not in self.words):
			self.words.append(word)
		
	def __str__(self):
		return (("%s > " % self.lemma) if self.lemma else '') + str(self.words)
	def __repr__(self):
		return "Family(%s)" % str(self)

	# перенаправить вызовы к массиву слов
	def __len__(self):
		return len(self.words)
	def __contains__(self, item):
		return self.words.__contains__(item)
	def __getitem__(self, key):
		return self.words.__getitem__(key)
	def __setitem__(self, key, value):
		return self.words.__setitem__(key, value)
	def __delitem__(self, key):
		return self.words.__delitem__(key)
	def __iter__(self):
		return self.words.__iter__()

# Основная функция: выделить семейства слов из словаря текста (несколько тысяч слов)
def make_word_families(dictionary, print_progress=True):
	families = []
	max_distance_within_family = 1.0;
	if print_progress: print('making word families ...\n.', end='')
	
	for w in dictionary:
		if print_progress: print("\b"+w[0], end='')
#         print(w,'...')
		min_distance_among_families = 999999;
		min_family_array = None;
		for family in families:
			avg_family_distance = 0;
			min_family_distance = 199;
			for word_of_family in family:
				d = distance_between(w,word_of_family);
#                 print(w,'-',word_of_family,":",d);
				if d > max_distance_within_family:
#                     print('break!')
					break;
				avg_family_distance += d;
				min_family_distance = min(min_family_distance, d)
			else: # no break in `for`
				avg_family_distance /= len(family);
#                 print('avg:',avg_family_distance);
				if(avg_family_distance < min_distance_among_families):
					min_distance_among_families = avg_family_distance;
					min_family_array = family;
			# force current family if at least one word has zero distance to w
			if min_family_distance == 0:
				min_family_array = family;
				break;
				
		# else: # no break in `for`
		if min_family_array != None:
			min_family_array.append(w);
		else:
			families.append( Family([w]) );
				
	return families;


# Найти леммы семейств (оставив только существительные в начальной форме) из списка слов семейства.
# Семейства, не приводящиеся в существительному или вообще не имеющие начальных форм в руссском языке, 
# будут иметь поле lemma, равное None
# @param families [in, out]
def find_lemmas(families):
	# c = collections.Counter()
	c = collections.defaultdict(lambda : 0)
	get_morph()

	for family in families:
		# # family_words = family["family"];
		
		norm_forms = [] # список кортежей (lemma, score)
		for word_form in family.words:
			norms = [(p.normal_form, p.score*(0.7 if {'anim'} in p.tag else 1)) # понижение рейтинга одушевлённых
					 for p in pymorphy2_morph.parse(word_form)  if {'NOUN'} in p.tag] # and 'sing' in p.tag]
	#         print(norms);
			norm_forms += norms;
		
		if not norm_forms: # не найдено ни одной начальной формы
			family.lemma = None # "пустая" лемма, нет леммы
			continue;

		# просуммировать при помощи счётчика
		c.clear();
		for lemma, score in norm_forms:
			c[lemma] += score
		
		# преобразовать из счётчика обратно в список кортежей
		scores = [(w,c[w]) for w in c];
		
		# отсортировать по возрастанию score
		scores.sort(key=lambda x:x[1]);
		
	    # взять лемму с максимальным score
		family.lemma = scores[-1][0]; # c.most_common(1)[0][0];
		# print(family["lemma"],": ", family);
		
	#     break
	return families


if __name__ == '__main__':
	#  test
	tf = Family(['альфа', 'бета'])
	print(tf)
	tf.words = ['альфа', 'бета', 'гамма']
	print(tf)
	tf.lemma = 'начальная'
	print(tf)
	print(len(tf))
	
	print(find_lemmas(make_word_families(['порог', 'порога', 'порожек', 'бег', 'бежать', 'побег'])))