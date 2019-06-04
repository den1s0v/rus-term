# coding=utf-8

from definition_pattern import *
from eval_utils import dump_data
from main_run import prepare_dir

if __name__ == '__main__':

    print('\n =========== START DEMO ===========\n')

    prepare_dir("result")

    book_dir = './text-corpus/'

    with open(book_dir+'patterns.txt', "r", newline="") as file:
        txt = file.read()
        
    print(len(txt), 'chars in text')

    main_chapter = Chapter(title="patterns", text=txt[-50000:]) # [-110000:]
    print(len(main_chapter), 'sentences in main_chapter')

    main_chapter.prepare_terms()
    
    
    # Init definition_pattern
    init_module(morph = main_chapter.get_morph())

    def_patterns = get_definition_patterns_extended('rule/definition_patterns.txt')

    print(len(def_patterns), "extended patterns read")

    if 'NO!' in "uniquelize lemmatized def patterns":
        def_ptt_lemm_set = set(map(normalize_pattern,def_patterns))
        # print(len(def_ptt_lemm_set), "def-patterns were read")

        #     Избавляемся от повторений паттернов лемм (сомнительная необходимость...)
        unique_lemmatized_def_ptts = []
        for lp in (map(lemmatize_def_ptt,def_ptt_lemm_set)):
            if any([ev.are_patterns_match(lp, p) for p in unique_lemmatized_def_ptts]):
                continue  # the same lemma pattern is already in list
            unique_lemmatized_def_ptts.append(lp)
            
        print(len(unique_lemmatized_def_ptts), "def-patterns remaining")
        def_patterns = unique_lemmatized_def_ptts


    fts = fill_def_ptts_with_terms(def_patterns, main_chapter.get_term_candidates(limit=None))
    print(len(fts), "filled def-patterns")
    # print([(t.normalized, t.term_inidices) for t in fts[::20]])

    print("Matching filled terms against chapter. Please wait...")

    def_matched = match_terms_against_chapter(main_chapter, fts)
    print(len(def_matched), "def-patterns matched")
    
    reversed_ts = match_terms([m[0] for m in def_matched], main_chapter.get_term_candidates(limit=None))
    print(len(reversed_ts), "source terms matched total:")
    sorted_rev_ts = sorted(reversed_ts.items(), key=lambda t:t[1], reverse=True)
    for t,n in sorted_rev_ts:
        print('\t', t.normalized.ljust(40), ":", n)

    # Save Results!
    min_entries = 2
    data_list = [ (t[0].normalized,t[1])  for t in sorted_rev_ts if t[1]>=min_entries]
    dump_data(data_list, 'result/def-%dterms-min%d.pkl' % (len(data_list), min_entries))
    print()

    # найти самые удачные шаблоны дефиниций
    reversed_ptts = rank_def_patterns([m[1] for m in def_matched], fts)
    sorted_rev_ptts = sorted(reversed_ptts.items(), key=lambda t:t[1], reverse=True)

    print(len(reversed_ptts), "most frequent def-patterns matched terms in text:")
    for t,n in (sorted_rev_ptts):
        print('\t', t.ljust(40), ":", n)
        
    print(sum([n for _,n in sorted_rev_ptts]), "total matches done with def-patterns")
    
    print("Done!")
