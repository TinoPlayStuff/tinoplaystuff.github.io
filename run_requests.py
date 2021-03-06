# run_requests.py
"""
!!! caution
this script will **delete** four folders:
  if your set "N_FDR" and "R_FDR" in the <-- setting --> block, this script will 
  delete all contents in the following four folders:
  "./_posts", "./_resources", "./_postsbak", and "./_resourcesbak"

This script will export your joplin notes and relative resource files according
to assigned tag. The exported files can be use by Jekyll.

Usage:
1. put this script in any folder 
2. create a file and put your joplin authorization token 
   (Tools -> Options -> Web Clipper -> Advanced options) into it.
3. modify the the <-- setting --> block in this script
4. run this script
5. find export result in ./_posts and ./_resources folders
"""

import os, subprocess, json
import datetime, re, shutil, uuid, requests, stat
from pathlib import Path

# <- setting
TOK_FILE = "run.py.tok"  # file contains joplin token
PUBTAG = "publishedev"  # note with this tag will be extracted
TAGHIDE = {"published", "publishedx",
           "publishedev"}  # test tags, will not be shown in exported posts
N_FDR = "./_posts"  # where to put the exported posts
R_FDR = "./_resources"  # where to put resource files (.jpg, .png, ...)
URL = "http://localhost:41184/"  # joplin web clipper service

# joplin resource folder, I know this is a bad practice, but its much
# faster than using joplin clipper protocal
JOPRFDR = "C:/_Greenware/joplin/joplinprofile/resources/"

# if True, the script search jtid:xxxx-xx-xx-asdfasdfaf in a note and use it as 
# the post title
IF_USED_JTID = True 

TAG_EXT = {'english_learning': {'英語學習'}}
# -> setting

#. regular expression for finding markdown link (need to be improved)
# INLINE_LINK_RE = re.compile(r'\[([^\]]+)\]\(:([^)]+)\)')
INLINE_LINK_RE = re.compile(r'\[.*\]\(\:.*\)')

#. regular expression for remove [TOC] lines
RM_TOC_RE = re.compile(r"^\[toc\] *\n", flags=re.MULTILINE | re.IGNORECASE)

#. regular expression for checking sub-sections
CHK_SECTION_RE = re.compile(r"^###* \S+.*", flags=re.MULTILINE)

# <- command string
GET_TAG = "curl -s " + URL + "tags/"
GET_NOTE = "curl -s " + URL + "notes/"
# TOK = "token=" + TOK
# -> command string

ID_DEST = {}  # mapping of id (markdown, resource) to dest
DEST_ID = {}  # reverse mapping from dest to id
ID_FDR = {}
ID_JTID = {}

link_not_published = []  # record of linked but not published notes
link_false = []  # reocrd of links pointing to nonexisting notes

req_sess = requests.Session()


# find the id of the specified id
def get_tag_id(_tag, tok):
  try:
    tags = req_sess.get(URL + "search?type=tag&query=" + _tag + "&" +
                        tok).json()['items']
  except Exception:
    return 'error'

  if len(tags) == 0:
    return None

  return tags[0]['id']


# check id and destination, add them into dictionaries
def check_add_dict(id, dest):
  # check if id-dest exists, if conflict to dicts
  if id in ID_DEST.keys():
    if ID_DEST[id] == dest:
      return 0
    else:
      return -1
  if dest in DEST_ID.keys():
    if DEST_ID[dest] == id:
      return 0
    else:
      return -1

  # add id-dest pair
  ID_DEST[id] = dest
  DEST_ID[dest] = id
  ID_FDR[id] = os.path.dirname(dest)

  return 1


def timestamp_to_date(timestamp, fmt):
  return datetime.datetime.fromtimestamp(int(timestamp) / 1000).strftime(fmt)


date_time_fmt = '%Y-%m-%dT%H:%M:%S+08:00'


def make_tag_line(note_id, tok):
  note_tags = json.loads(
      subprocess.Popen(GET_NOTE + note_id + "/tags?" + tok + "&limit=100",
                       stdout=subprocess.PIPE).stdout.read())
  #^ a note shouldn't have more than 100 tags ...

  tag_set = {ii['title'] for ii in note_tags['items']}
  tag_set = tag_set - TAGHIDE

  #. add extended tags
  for k in TAG_EXT.keys():
    if k in tag_set:
      tag_set = tag_set | TAG_EXT[k]

  return "tags: [" + ", ".join(x for x in tag_set) + "]"


def cvt_resource_link(doc, note_id, tok):
  res = json.loads(
      subprocess.Popen(GET_NOTE + note_id + "/resources?" + tok +
                       "&fields=id,file_extension&limit=100",
                       stdout=subprocess.PIPE).stdout.read())
  #^ currently, only convert 100 resources
  for i in res['items']:
    rid = i['id']
    ori_str = ':/' + rid
    res_dest = ID_DEST[rid]
    new_link_url = os.path.relpath(res_dest, ID_FDR[note_id])
    doc = doc.replace(ori_str, Path(new_link_url).as_posix())

  return doc


def travel_tag_notes(tag_id, tok, n=1):
  #. get all notes with PUBTAG
  notes = json.loads(
      subprocess.Popen(
          GET_TAG + tag_id + "/notes?" + tok +
          "&fields=id,parent_id,title,user_created_time,user_updated_time,body"
          + "&limit=100&page=" + str(n),
          stdout=subprocess.PIPE).stdout.read())

  #. for each note
  for note in notes['items']:
    note_id = note['id']

    tag_line = make_tag_line(note_id, tok)

    note_dest = ID_DEST[note_id]
    doc = note['body']

    # last_modified_at: 2016-03-09T16:20:02-05:00
    last_modified_line = "last_modified_at: " + datetime.datetime.fromtimestamp(
        int(note['user_updated_time']) / 1000).strftime(date_time_fmt)
    #^ for minimal mistake theme to do something (may be omitted)

    # last_updated_line = "last_updated: " + datetime.datetime.fromtimestamp(
    #     int(note['user_updated_time']) /
    #     1000).strftime(date_time_fmt)
    # #^ for jekyll sort post (may be omitted if set the folowing "date" tag)

    created_date_line = "created_date: " + datetime.datetime.fromtimestamp(
        int(note['user_created_time']) / 1000).strftime(date_time_fmt)

    date_line = "date: " + datetime.datetime.fromtimestamp(
        int(note['user_updated_time']) / 1000).strftime(date_time_fmt)
    #^ for jekyll's pagination to sort post
    # https://talk.jekyllrb.com/t/sort-posts-by-updated-and-published-date/6789/2
    # https://cynthiachuang.github.io/Show-the-Last-Modified-Time-in-Jekyll-NextT-Theme/

    #. convert resource link
    #! this must be done before convert markdown link
    #  because the resouce list is reported by joplin api
    #  deal it first, then my own code don't have to distinguish them
    #  why distinguish resource and markdown link?
    #    for resource, we only copy it
    #    for markdown, we need to generate it
    doc = cvt_resource_link(doc, note_id, tok)

    #. convert markdown link
    #! note: this use simple pattern to find markdown links
    in_links = INLINE_LINK_RE.findall(doc)
    for link in in_links:
      s = link.rfind("/")
      e = link.rfind("#")
      if e < s:
        link_id = link[s + 1:-1]
        e = -1
      else:
        link_id = link[s + 1:e]

      # deal if the link is not published or invalid
      if link_id not in ID_DEST.keys():
        try:
          #. if the link is a no published note ...
          ex_note = json.loads(
              subprocess.Popen(GET_NOTE + link_id + "?" + tok +
                               "&fields=title,source_url",
                               stdout=subprocess.PIPE).stdout.read())["title"]
          ex_note = "[" + ex_note + "] linked in [" + note['title'] + "]"
          link_not_published.append(ex_note)
          doc = doc.replace(link[s - 2:],
                            ' <- "not ready yet, maybe come here later" ')
          # maybe use source_url?
        except Exception:
          #. if the link is invalid (maybe sample in code block)
          link_false.append("fake link [" + link_id + "] shown in [" +
                            note['title'] + "]")
          print('seems invalid markdown link\n')
          # maybe use source_url?
        continue

      link_dest = ID_DEST[link_id]
      new_link_url = os.path.relpath(link_dest, ID_FDR[note_id])
      new_link_url = Path(new_link_url).as_posix()
      new_link = link[0:s - 1] + new_link_url + link[e:]
      #^! why note use .replace? this may be safer

      doc = doc.replace(link, new_link)

    #. remove [toc] line
    doc = RM_TOC_RE.sub("\n", doc)

    #. hide contents not for read
    if doc.find('\n-- end --') != -1:
      doc = doc.replace("\n-- end --",
                        '<span style="color:LightGray">\n-- end --')
      # doc = doc + '</span>\n'

    yaml_head = "---\n"
    yaml_head += tag_line + "\n"
    yaml_head += last_modified_line + "\n"
    # yaml_head += last_updated_line + "\n"
    yaml_head += created_date_line + "\n"
    yaml_head += date_line + "\n"

    if len(CHK_SECTION_RE.findall(doc)) == 0:
      yaml_head += "toc: false\n"

    yaml_head += "---\n"
    os.makedirs(os.path.dirname(note_dest), exist_ok=True)
    f = open(note_dest, "w", encoding="utf-8")
    f.write(yaml_head)
    f.write(doc)
    f.close()

  if notes['has_more']:
    return travel_tag_notes(tag_id, tok, n + 1)
  else:
    return True


def add_resource(note_id, tok, n=1):
  #. get resource list
  # res = json.loads(
  #     subprocess.Popen(GET_NOTE + note_id + "/resources?" + TOK +
  #                      "&fields=id,file_extension&limit=100&page=" + str(n),
  #                      stdout=subprocess.PIPE).stdout.read())
  res = req_sess.get(URL + "notes/" + note_id + "/resources?" + tok +
                     "&fields=id,file_extension&limit=100&page=" +
                     str(n)).json()

  for i in res['items']:
    #. get id
    id = i['id']

    #. get dest
    new_fname = id + '.' + i['file_extension']
    res_dest = os.path.join(R_FDR, id[-2:], new_fname)

    # #. copy resource
    # # subprocess.Popen("curl -s -o " + res_dest + " " + URL + "resources/" + id +
    # #                  "/file?" + TOK,
    # #                  stdout=subprocess.PIPE).stdout.read()
    # if os.path.exists(res_dest):
    #   # subprocess.run("curl -s -z -o " + res_dest + " " + URL + "resources/" + id +
    #   #                "/file?" + TOK)
    #   # subprocess.Popen("curl -s -z -o " + res_dest + " " + URL + "resources/" +
    #   #                  id + "/file?" + TOK,
    #   #                  stdout=subprocess.PIPE).stdout.read()
    #   pass
    # else:
    #   # subprocess.Popen("curl -s -o " + res_dest + " " + URL + "resources/" +
    #   #                  id + "/file?" + TOK,
    #   #                  stdout=subprocess.PIPE).stdout.read()
    #   shutil.copy2(JOPRFDR+new_fname, res_dest)

    #. id-dest dictionary creation
    o = check_add_dict(id, res_dest)
    if o == -1:
      return False

    # a news resource, copy it
    if o == 1:
      srcfile = JOPRFDR + new_fname
      os.makedirs(os.path.dirname(res_dest), exist_ok=True)
      if os.path.exists(res_dest):
        if os.stat(srcfile).st_mtime - os.stat(res_dest).st_mtime > 1:
          shutil.copy2(srcfile, res_dest)
      else:
        shutil.copy2(JOPRFDR + new_fname, res_dest)

  if res['has_more']:
    return add_resource(id, tok, n + 1)
  else:
    return True


#. ^jtid:\S+
FIND_JTID_RE = re.compile(r'^jtid:\S+', flags=re.MULTILINE | re.IGNORECASE)


def decide_dest(note, note_id):
  #. dest
  time_str_ = timestamp_to_date(note['user_created_time'], '%Y-%m-%d') + "-"
  YY_MM = time_str_[0:4]

  if IF_USED_JTID:
    #. get jtid from note
    jtid = FIND_JTID_RE.findall(note['body'])
    if len(jtid) > 0:
      jtid = jtid[-1]

      # if jtid not match note's time, show warning
      if jtid[5:16] != time_str_:
        input("\ncurrent post time: " + time_str_ + " not match " + jtid +
              "\nnote title: " + note['title'] + '\npress [enter] to continue')
      new_fname = jtid[5:] + '.md'
    else:
      new_fname = time_str_ + str(uuid.uuid4()) + '.md'
    ID_JTID[note_id] = "jtid:" + new_fname[0:-3]
  else:
    new_fname = time_str_ + str(uuid.uuid4()) + '.md'
    #. Q: why not use timestamp?
    #  A: because if the notes are created by "import",
    #     the timestamp may not be unique.
    #  Q: why not use title?
    #  A: because I am too lazy to implement it.

  note_dest = os.path.join(N_FDR, YY_MM, new_fname)

  return note_dest


# generate id(note)-dest dictionary
# dest is timebased
def travel_tag_notes_pre(tag_id, TOK, n=1):
  #. get notes with PUBID
  # notes = json.loads(
  #     subprocess.Popen(
  #         GET_TAG + tag_id + "/notes?" + TOK +
  #         "&fields=id,parent_id,title,user_created_time,user_updated_time,body&page="
  #         + str(n),
  #         stdout=subprocess.PIPE).stdout.read())
  notes = req_sess.get(
      URL + "tags/" + tag_id + "/notes?" + TOK +
      "&fields=id,parent_id,title,user_created_time,user_updated_time,body&page="
      + str(n)).json()

  for note in notes['items']:
    print('\x1b[1K\r', note['title'], end='')

    #. id
    note_id = note['id']

    #. dest
    note_dest = decide_dest(note, note_id)

    #. note_id-dest dictionary creation
    o = check_add_dict(note_id, note_dest)
    if o == -1:
      return False

    #. also add resource-dest into dictionary
    o = add_resource(note_id, TOK)
    if not o:
      return False

  if notes['has_more']:
    return travel_tag_notes_pre(tag_id, TOK, n + 1)
  else:
    return True


def del_rw(action, name, exc):
  if os.path.exists(name):
    os.chmod(name, stat.S_IWRITE)
    os.remove(name)


def main():
  # 0. get token
  try:
    with open(TOK_FILE) as f:
      TOK = "token=" + f.read().strip()
  except Exception:
    print('\nFAILED: check your "TOK_FILE" setting\n')
    return

  # 1. get publication tag's id
  PUBTAGID = get_tag_id(PUBTAG, TOK)
  if PUBTAGID == 'error':
    print("\n\n\nmaybe check your token ...")
    return
  if PUBTAGID is None:
    print("\n\n\nno note has tag: ", PUBTAG)
    return

  # 2. create output folders
  if os.path.exists(N_FDR):
    shutil.rmtree(N_FDR + "bak", True)
    shutil.move(N_FDR, N_FDR + "bak")
  if os.path.exists(R_FDR):
    shutil.rmtree(R_FDR + "bak", onerror=del_rw)
    shutil.move(R_FDR, R_FDR + "bak")
  os.makedirs(N_FDR, exist_ok=True)
  os.makedirs(R_FDR, exist_ok=True)

  # 3. see all notes with pubtag, generate id-dest dictionary
  ret = travel_tag_notes_pre(PUBTAGID, TOK)
  if not ret:
    print("\n\n\nsome thing wrong: maybe duplicate id\n\n")

  # 4. extract notes and resources
  travel_tag_notes(PUBTAGID, TOK)

  # 5. report unusual links
  print("\n", *link_not_published, "", *link_false, sep="\n", end="\n\n\n")
  with open(r'./run.py.log', 'w', encoding="utf-8") as fp:
    fp.write('## linked notes have not tag: ' + PUBTAG + ': \n\n- ')
    fp.write('\n- '.join(link_not_published))
    fp.write('\n\n\n')
    fp.write('## not existed links: \n\n- ')
    fp.write('\n- '.join(link_false))

  print('done')


if __name__ == '__main__':
  s = datetime.datetime.now().strftime('%H:%M:%S')
  main()
  print(s, " -> ", datetime.datetime.now().strftime('%H:%M:%S'))
