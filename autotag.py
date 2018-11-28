#!/usr/bin/python3
import json
import logging
import os
import sqlite3
import time

import requests
import saucenao.exceptions
import urllib3
from libxmp import XMPFiles, XMPMeta, consts
from saucenao.saucenao import SauceNao

folder_path = 'your_media_folder_path like /mnt/nas/images/'
if (folder_path[-1] is '/' or folder_path[-1] is '\\'):
    folder_path = folder_path[:-1]
saucenao_api_key = 'your_saucenao_api_key'
danbooru_login = 'your_danbooru_username'
danbooru_api_key = 'your_danbooru_api_key'


def search(saucenao_core, filepath):
    result = saucenao_core.check_file(filepath)
    return result


def worker(filepath):
    # initialize saucenao
    saucenao_core = SauceNao(directory='directory',
                             databases=9,
                             # 999 by default, 5 for pixiv, 9 for booru.
                             minimum_similarity=65,
                             combine_api_types=False,
                             api_key=saucenao_api_key,
                             exclude_categories='',
                             move_to_categories=False,
                             use_author_as_category=False,
                             output_type=SauceNao.API_JSON_TYPE,
                             start_file='', log_level=logging.ERROR,
                             title_minimum_similarity=90)
    # search image on saucenao
    try:
        result = search(saucenao_core, filepath)
    except requests.exceptions.ConnectionError:
        print("Failed to connect saucenao!")
        return -1
    except saucenao.exceptions.DailyLimitReachedException:
        print("Saucenao daily limit reached! try 1 hour later!")
        return -2
    if (len(result) is 0):
        print('Image not found on danbooru!')
        return 1
    else:
        danbooru_id = result[0]['data']['danbooru_id']
        print('Image Found, ID=' + str(danbooru_id))
        # GET danbooru tag json
        try:
            http = urllib3.PoolManager()
            # disable  https cert check warning
            urllib3.disable_warnings(
                urllib3.exceptions.InsecureRequestWarning)
            url = 'https://danbooru.donmai.us/posts/' + str(danbooru_id) + '.json'
            headers = urllib3.util.make_headers(basic_auth=danbooru_login + ':' + danbooru_api_key)
            r = http.request('GET', url, headers=headers)
            r_data = r.data
            if isinstance(r_data, bytes):
                r_data = str(r_data, 'utf-8')
            tags = json.loads(r_data)['tag_string']
            taglist = tags.split()
        except requests.exceptions.ConnectionError:
            print('failed to GET tag data from danbooru')
            return -1
        # Write XMP Metadata to image
        xmpfile = XMPFiles(file_path=filepath,
                           open_forupdate=True)
        xmp = xmpfile.get_xmp()
        # if image has no xmp data, create one
        if (xmp is None):
            xmp = XMPMeta()
        # write the tags
        for each in taglist:
            # check whether XMP includes 'subject' property,
            # if not, create a new one
            if (not xmp.does_property_exist(consts.XMP_NS_DC, 'subject')):
                xmp.append_array_item(consts.XMP_NS_DC, 'subject',
                                      each,
                                      {'prop_array_is_ordered': True,
                                       'prop_value_is_array': True})
            # check whether tag has been written to file
            if (not xmp.does_array_item_exist(consts.XMP_NS_DC,
                                              'subject', each)):
                xmp.append_array_item(consts.XMP_NS_DC, 'subject', each)
        if (xmpfile.can_put_xmp(xmp)):
            xmpfile.put_xmp(xmp)
            xmpfile.close_file()
            return 0
        else:
            print('Unable to write XMP data!')
            return -1


def main():
    # connect and create to local database
    #  cx = sqlite3.connect('task.db', isolation_level=None)
    cx = sqlite3.connect('task.db')
    #  cx = sqlite3.connect(':memory:', isolation_level=None)
    cu = cx.cursor()
    cu.execute("CREATE TABLE IF NOT EXISTS FILELIST \
               (ID INTEGER PRIMARY KEY AUTOINCREMENT, \
               FILE_PATH TEXT NULL UNIQUE, \
               STATUS INTEGER)")
    # format folder path
    files = os.listdir(folder_path)
    image_extension_names = ['.jpg', '.jpeg',
                             '.gif', '.bmp', '.png', '.tiff', '.webp']
    # add image to database
    print("Adding image to the database...")
    for file in files:
        if (not os.path.isdir(file)) and \
                os.path.splitext(file)[-1] in image_extension_names:
            filepath = folder_path + "/" + file
            t = (filepath, 0)
            try:
                cu.execute('INSERT INTO FILELIST VALUES (NULL,?,?)', t)
            except sqlite3.IntegrityError:
                print('[Existed]' + filepath)
            else:
                print('[  New  ]' + filepath)

    # Re-add network failed images into unsynced files
    cu.execute("UPDATE FILELIST set STATUS=0 where STATUS=-1")

    # Periodically query the first unsynced filename, do the tagging
    print("-----------------------------------")
    print("Searching image data on danbooru...")
    cu.execute('SELECT COUNT(*) FROM FILELIST where STATUS=0')
    Cnt = cu.fetchone()[0]
    while (Cnt > 0):
        cu.execute('SELECT * FROM FILELIST where STATUS=0 LIMIT 1')
        record = cu.fetchone()
        filepath = record[1]
        print(filepath)
        ret = worker(filepath)
        if ret is 1:
            cu.execute("UPDATE FILELIST set STATUS=2 where ID=?",
                       (record[0],))
        # ret==0 sucessfully added tags
        elif ret is 0:
            cu.execute("UPDATE FILELIST set STATUS=1 where ID=?",
                       (record[0],))
        # ret==-1 failed caused by network problems
        elif ret is -1:
            cu.execute("UPDATE FILELIST set STATUS=-1 where ID=?",
                       (record[0],))
        # ret==-2 saucenao daily limit reached, try the same picture again later
        elif ret is -2:
            print("Waiting for next retry...")
            time.sleep(3600)

        cx.commit()
        cu.execute('SELECT COUNT(*) FROM FILELIST where STATUS=0')
        Cnt = cu.fetchone()[0]
    print('All work has been done!')
    cu.execute('SELECT COUNT(*) FROM FILELIST')
    Cnt_all = cu.fetchone()[0]
    cu.execute('SELECT COUNT(*) FROM FILELIST where STATUS=1')
    Cnt_success = cu.fetchone()[0]
    cu.execute('SELECT COUNT(*) FROM FILELIST where STATUS=-1')
    Cnt_next = cu.fetchone()[0]
    print("Result: " + str(Cnt_all) + " total, " + str(Cnt_success) +
          " found, " + str(Cnt_next) + " will be tagged next time.")


if __name__ == "__main__":
    main()
