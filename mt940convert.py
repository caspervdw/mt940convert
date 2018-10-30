#!/usr/bin/env python
# coding: utf-8
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

from argparse import ArgumentParser
import csv

parser = ArgumentParser(
    description='Tool for converting ING csv to MT940',
)

parser.add_argument(
    'filename',
    help='Input filename'
)


parser.add_argument(
    '-r', '--reknr',
    dest='reknr',
    help='Account number as configured in accounting system'
)

parser.add_argument(
    '-d', '--date',
    dest='date',
    help='Date before first transaction date (JJMMDD)'
)


def count_quotes(header, sep=','):
    """ count how many quotes are there on both sides of each field"""
    header_splitted = header.split(sep)
    count_left = [0] * len(header_splitted)
    count_right = [0] * len(header_splitted)
    for i, col in enumerate(header_splitted):
        while col[count_left[i]] == '"':
            count_left[i] += 1
        while col[-count_right[i]-1] == '"':
            count_right[i] += 1
    return count_left, count_right


def fix_quotes(line, count_left, count_right, sep=','):
    elems = []
    for left, right in zip(count_left, count_right):
        start = left
        if right == 0:
            stop = line.find(sep, start)
            next_start = stop + len(sep)
        else:
            stop = line.find('"' * right, start)
            next_start = stop + right + len(sep)
        elems.append('"' + line[start:stop] + '"')
        line = line[next_start:]
    return sep.join(elems)


def run_conversion(filename_in, reknr, firstdate):
    filename_out = filename_in.replace('.csv', '.ing')

    if len(firstdate) != 6:
        raise ValueError('First date should be given YYMMDD')

    header_mt940 = """0000 01INGBNL2AXXXX00001
    0000 01INGBNL2AXXXX00001
    940 00
    :20:INGEB
    :25:{reknr}
    :28C:1
    :60F:C{firstdate}EUR0
    """.format(reknr=reknr, firstdate=firstdate).replace('\n', '\r\n')


    # check if the quotes are OK (issue introduced by ING after ~1-1-2017)
    # avoiding these kind of lines:
    # '"Datum,""Naam / Omschrijving"",""Rekening"",""Tegenrekening"",""Code"",
    #  ""Af Bij"",""Bedrag (EUR)"",""MutatieSoort"",""Mededelingen"""\r\n'
    with open(filename_in, 'rt') as openfile:
        header = openfile.readline()[:-1]
        quotes_left, quotes_right = count_quotes(header)
        if not (all([q == 1 for q in quotes_left])
                and all([q == 1 for q in quotes_right])):
            filename_conv = filename_in.replace('.csv', '_repaired.csv')
            with open(filename_conv, 'wt', newline='\r\n') as outfile:
                outfile.write(fix_quotes(header, quotes_left, quotes_right) + '\n')
                for line in openfile.readlines():
                    outfile.write(fix_quotes(line, quotes_left, quotes_right) + '\n')
        else:
            filename_conv = filename_in

    with open(filename_conv, 'r') as openfile:
        reader = csv.reader(openfile)
        for row in reader:
            break

        result = header_mt940
        saldo = 0
        for row in reader:
            date, name, _, iban, typ, DC, amount, _, comment = row
            cents = int(float(amount.replace(',', '.')) * 100)
            if DC == 'Bij':
                DC = 'C'
                saldo += cents
            else:
                DC = 'D'
                saldo -= cents
            result += ':61:' + date[2:] + DC + amount + 'N' + typ + '\r\n'
            if len(comment) > 0:
                result += ':86:' + comment[:63] + '\r\n'
            if len(comment) > 63:
                result += ':86:' + comment[63:126] + '\r\n'

    if saldo > 0:
        DC = 'C'
    else:
        DC = 'D'
    saldo_str = '{0:.2f}'.format(saldo / 100.).replace('.', ',')
    result += ":62F:" + DC + date[2:] + "EUR" + saldo_str + '\r\n-'

    with open(filename_out, 'w') as openfile:
        openfile.write(result)

    return filename_out


if __name__ == '__main__':
    args = parser.parse_args()
    out = run_conversion(args.filename, args.reknr, args.date)
    print("MT940 file has been written to {}".format(out))
