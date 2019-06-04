# -*- coding:utf-8

import re

T_CYR = 'Т'
T_LAT = 'T'
T_OPT = 'T?' # lat T

re_hash_comment = re.compile(r"\s*#.*$")  # no MULTILINE option
re_T = re.compile(r'\b'+('|'.join((T_CYR,T_LAT)))+r'\b')

# Main function to export
def get_definition_patterns_extended(filename="definition_patterns.txt"):
    def_patterns = load_hash_commented_file(filename, cut_eol_comment=True)
    def_patterns = extend_definition_patterns(def_patterns)
    return def_patterns
    

def load_hash_commented_file(filename, keep_empty_lines=False, cut_eol_comment=False):
    """ get list of lines (strings) """
    lines = []
    with open(filename, encoding='utf-8') as f:
        for line in f:
            if re_hash_comment.match(line):
                continue # commented line
            if cut_eol_comment:  # and re_hash_comment.search(line):
                line = re_hash_comment.sub("", line)
            if line.endswith('\n'):
                line = line[:-1] # strip last char
            if not keep_empty_lines and not line:
                continue # empty line
            lines.append(line)
    return lines

# def_patterns = load_hash_commented_file(def_patt_file, cut_eol_comment=True)
# print(len(def_patterns), 'definition patterns found')
# def_patterns


def extend_definition_pattern(ptt_str):
    """
        Преобразует подстановки вида 'Т?' в ptt_str, заменяя на Т иил убирая вовсе.
        В результате списком выдаются все варианты подстановок, в которых есть хотя бы одна Т.
        * Все Т на выходе - латинские, на входе допускаются обе: лат. и кириллицей (но только заглавные!).
    """
    ptt_str = re_T.sub(T_LAT, ptt_str)
    
    opt_num = ptt_str.count(T_OPT)
    pure_T_num = ptt_str.count(T_LAT) - opt_num
    #     print(pure_T_num)
    if opt_num == 0 | opt_num == 1 & pure_T_num == 0:
        return [ptt_str.replace(T_OPT, T_LAT)] # unique combination available
    
    pieces = ptt_str.split(T_OPT)
    ptts = []
    start_k = (1  if pure_T_num == 0 else  0)
    for k in range(start_k, 2**opt_num): # iterate over all combinations, but if there`s no pure T, exclude the first 1 (fully empty)
        opts = [k & (1<<i) for i in range(opt_num)]
        ptt = pieces[0]
        for i in range(opt_num):
            ptt += (T_LAT if opts[i] else '') + pieces[i+1]
        ptts.append(ptt.strip())
        
    return ptts
    
# extend_definition_pattern(def_patterns[4])

def extend_definition_patterns(ptt_list):
    res_list = []
    for ptt_str in ptt_list:
        res_list.extend( extend_definition_pattern(ptt_str) )
    return res_list
        

# def_patterns2 = extend_definition_patterns(def_patterns)
# print(len(def_patterns2), 'definition patterns got')
# def_patterns2
