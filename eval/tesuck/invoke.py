#!/usr/bin/env python
# -*- coding: utf-8 -*-
 
# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://sam.zoy.org/wtfpl/COPYING for more details.

import argparse
import httplib, urllib
from urlparse import urlparse

parser = argparse.ArgumentParser(description='Invoke Tesuçk.')
parser.add_argument('-o', '--output', required=True,
                    help='Output file name')
parser.add_argument('-i', '--input', required=True,
                    help='Input file name')
parser.add_argument('-l', '--language', required=True, default='ru',
                    help='Preferred language (ru, en)')
parser.add_argument('-a', '--approach', default='textrank',
                    help='Preferred approach (degext, textrank)')
parser.add_argument('-w', '--window', type=int, default=2,
                    help='Specify the words window')
parser.add_argument('-e', '--endpoint',
                    default='http://tesuck.eveel.ru/extract.graphml',
                    help='Endpoint URI')
args = parser.parse_args()

with open(args.input, 'r', encoding='utf-8') as input:
    text = input.read()

url = urlparse(args.endpoint)

params = urllib.urlencode({
    'text': text,
    'language': args.language,
    'approach': args.approach,
    'window': args.window
})

headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Accept': 'text/plain'
}

conn = httplib.HTTPConnection(url.netloc)
conn.request('POST', url.path, params, headers)

response = conn.getresponse()
data = response.read()

with open(args.output, 'w', encoding='utf-8') as output:
  output.write(data)

conn.close()