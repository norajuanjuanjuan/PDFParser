import pdfplumber
import re
import os
import xlrd
from xlutils.copy import copy
import threading
import time
import multiprocessing
from datetime import datetime


def search_tables(path):
    print('load file:', os.path.basename(path))
    pdf = pdfplumber.open(path)
    pages = pdf.pages
    print('total page:', len(pages))
    print('searching pdf...')
    target = []
    for ind, page in enumerate(pages):
        # print('parse page:', ind + 1)
        text = page.extract_text()
        lines = re.split(r'\n+', text)
        for index, line in enumerate(lines):
            if re.match(r'\s*\d+[、.\s]+税金及附加\s*$', line):
                tables = page.extract_tables()
                for table in tables:
                    row = re.sub(r'\s+', '', ''.join([item if item is not None else '' for item in table[0]]))
                    next = lines[index + 1]
                    cnt = index + 1
                    while cnt < len(lines) and re.search(r'适用|不适用|单位.*元', next):
                        cnt += 1
                        next = lines[cnt]
                    if re.sub(r'\s+', '', next) == row:
                        target.append(table)
                        if '合计' not in str(table):
                            tables = pages[ind + 1].extract_tables()
                            if isinstance(tables, list) and len(tables) > 0:
                                target.append(tables[0])
                                return target
    return target


def target(tables, rules):
    target_info = []
    for table in tables:
        for row in table:
            for rule in rules:
                if row[0] is not None and re.sub(r'\s+|\n+', '', row[0]) == rule:
                    target_info.append(row)
    return target_info


def save(info, out_path, rules, code, name):
    print('save to file:', os.path.basename(out_path))
    book = xlrd.open_workbook(out_path)
    cbook = copy(book)
    sheet = book.sheet_by_index(0)
    csheet = cbook.get_sheet('Sheet1')

    csheet.write(sheet.nrows, 0, str(code))
    csheet.write(sheet.nrows, 1, str(name))
    for ind, one in enumerate(info):
        if not isinstance(one, list) or len(one) < 2:
            continue
        for index, rule in enumerate(rules):
            if one[0] == rule:
                csheet.write(sheet.nrows, index + 2, str(one[1]))
    cbook.save(out_path)


def load_demo(path):
    print('load demo Excel:', os.path.basename(path))
    book = xlrd.open_workbook(path)
    sheet = book.sheet_by_index(0)
    row = sheet.row_values(1, 0, sheet.ncols)
    return row


def folder(folder_path):
    paths = []
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for file in filenames:
            path = os.path.join(dirpath, file)
            if os.path.isfile(path) and (os.path.splitext(path)[1] == '.pdf' or os.path.splitext(path)[1] == '.PDF'):
                paths.append(path)
    return paths


def run(path, row, lock):
    # print('processing on file:', os.path.basename(path))
    pdf = os.path.basename(path)
    rule = row[2:]
    code = pdf.split('-')[1]
    name = re.split(r'[\-:：]+', pdf)[-2]
    try:
        tables = search_tables(path)
    except Exception as e:
        print('parse pdf error:', e)
        with open('errorList.txt', 'a', encoding='utf-8') as fp:
            fp.write('parse pdf error:' + path + '\n')
        return
    try:
        info = target(tables, rule)
        if not isinstance(info, list) or len(info) < 1:
            print('find nothing in file:', pdf)
            with open('errorList.txt', 'a', encoding='utf-8') as fp:
                fp.write('find nothing in file:' + path + '\n')
            return
    except Exception as e:
        print('search table error:', e)
        with open('errorList.txt', 'a', encoding='utf-8') as fp:
            fp.write('search table error:' + path + '\n')
        return
    try:
        lock.acquire()
        save(info, demo, rule, code, name)
        lock.release()
    except Exception as e:
        print('Do you open the Demo Excel? Please close it.The program will save again after 30 seconds...')
        time.sleep(30)
        try:
            lock.acquire()
            save(info, demo, rule, code, name)
            lock.release()
        except Exception as e:
            print('save error:', e)
            with open('errorList.txt', 'a', encoding='utf-8') as fp:
                fp.write('save error:' + path + '\n')


def multi_threads(paths, row):
    th_pool = []
    lock = threading.Lock()
    for i, path in enumerate(paths):
        th = threading.Thread(target=run, args=(path, row, lock))
        th.start()
        th_pool.append(th)
    for th in th_pool:
        th.join()


def batch_parser(paths, demo):
    try:
        row = load_demo(demo)
    except Exception as e:
        print('load Excel error:', e)
        return
    pool = multiprocessing.Pool(processes=4)
    for i in range(0, len(paths), 5):
        path = paths[i:(i + 5 if (i + 5 <= len(paths) - 1) else len(paths) - 1)]
        pool.apply_async(func=multi_threads, args=(path, row))
    pool.close()
    pool.join()


if __name__ == '__main__':
    # paras
    base_dir = r'C:\Users\fanyu\Desktop\PaidProject\16_Tables_PDF_extractor'
    demo = r'C:\Users\fanyu\Desktop\PaidProject\16_Tables_PDF_extractor\Demo.xls'
    with open('errorList.txt', 'w', encoding='utf-8')as fp:
        fp.write(str(datetime.now()) + '\n\n')
    try:
        paths = folder(base_dir)
        batch_parser(paths, demo)
    except Exception as e:
        print('load pdf error:', e)
    print('Program finished!')
