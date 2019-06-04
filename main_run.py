# coding=utf-8

import argparse
import os

from text_utils import *

def parse_cmdline():
    """Parses command line arguments and returns an object with fields (of type string):
        textfile path     (for -p option)
        sent_by_part      (for -s option)
        query             (for -q option)
        limit             (for -l option)
        OverwriteArticles (for -w option)
        toSleep           (for -s option)
        Timeout           (for -to option)
        QuietLog          (for -ql option)

    """
    parser = argparse.ArgumentParser(
        description='Extract terms in Russian from a textfile'
    )
    parser.add_argument("PATH", # "-p",
                        help="Textfile path")
    parser.add_argument("--sent_by_part", "-s",
                        help="Sentences number by each part by whose the text is splitted, or space separated list of such numbers",
                        nargs='+', type=int,
                        default=[40],
                        required=False)
    parser.add_argument("--min_count", "-m",
                        default=5,
                        type=int,
                        help="Minimum count of term in the text (default: 5)",
                        required=False)
    parser.add_argument("--limit", "-l",
                        default=None,
                        type=int,
                        help="Keep only first L terms for bootstrapping further intersection of algorithm (default: no limit)",
                        required=False)
    args = parser.parse_args()

    return args

def prepare_dir(dir):
    """Checks the path and creates a directory if nesessary.
    If path does exist and is not a directory,
    or specified location is not writable, an exception is trown.

    """
    if not os.path.exists(dir):
        # create a directory tree
        try:
            os.makedirs(dir, exist_ok=True)
        except Exception as e:
            terminate_with_error(str(e) + '\n\tOccured while preparing dir:',dir)
        print('Dir created.')
    else:
        # check write permission
        if not os.access(dir, os.F_OK | os.W_OK):
            terminate_with_error("directory is not accessible or writable: "+dir)


def process_text(txt, sent_by_part_list=[40], min_count=None, sieve_limit=50):
    """ process_text(txt, min_count=2, sent_by_part_list=[40], min_count=5, sieve_limit=50)
    -> sorted list[str]   """
    work_chapter = Chapter()
    results = work_chapter.run_on_text(txt, sent_by_part_list, min_count=min_count, limit=sieve_limit)
    
    print("Ranking algorithms finished:")
    for k in results.keys():
        print('\t', k)
        
    term_sets = [
        {w for w,_ in ts} for ts in results.values()
    ]
    print("Intersecting", len(term_sets), "rankings ...")
        
    common_terms = term_sets[0]
    for s in term_sets[1:]:
        common_terms = common_terms.intersection(s)
        
    print(len(common_terms), "terms remaining after intersection")

    common_terms = list(common_terms)
    common_terms.sort()
    
    return common_terms


if __name__ == '__main__':
    
    print('\n =========== TERM EXTRACTION START ===========\n')

    args = parse_cmdline()


    prepare_dir("result")


    print("Startup parameters:")
    print()
    for k in ('PATH','sent_by_part','limit','min_count'):
        print(k.rjust(15),":",getattr(args,k))
    
    try:
        with open(args.PATH, "r", newline="") as file:
            txt = file.read()
    except Exception as e:
        print("Error!")
        print(e)
        exit()
        
        
    print(len(txt) // 1024, 'kBytes of text loaded.')
    print()
    
    terms = process_text(txt, sent_by_part_list=args.sent_by_part, min_count=args.min_count, sieve_limit=args.limit)
    
    save_path = "result/extracted-min%d%s.txt" % (args.min_count, ("-lim%d" % args.limit) if args.limit else "")
    
    with open(save_path, "w", newline="") as file:
        file.write("# Source text: "+args.PATH+"\n")
        file.write("# Parameters :")
        file.write( " sent_by_part="+ (','.join(map(str,args.sent_by_part))) )
        file.write( " limit="+ str(args.limit) )
        file.write( " min_count="+ str(args.min_count) )
        file.write("\n")
        file.write( "# Terms extracted: "+ str(len(terms)) )
        file.write("\n\n")
        
        file.write("\n".join(terms))
        file.write("\n")
    
    
    print('Saved result:', save_path)

    print('\n =========== TERM EXTRACTION END ===========\n')
