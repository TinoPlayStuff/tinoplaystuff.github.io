#!/usr/bin/python3
import sys, glob, os, subprocess, json
from pathlib import Path
import datetime, re

#. token from joplin -> Tool -> Options -> Web Clipper -> Authorization token:
TOK = "4ccabec736a39dcfeac27efc8ab253ca4760c7aeb2bd468b5932e2e2c181b08557a507081f88fb0a80efb66650fc09b9fde7c4202f437cf73b79c18c55e0456a"
# TOK = "4444503f811297abb7e0819eb3b32c33a3c7542a50325233ea6eff9889b4315bc437621aca8b90221b553d3bb0358a4d6e4b3225849d483c87394d18df38bf1e"

PUBTAG = "published"  # note with this tag will be extracted
N_FDR = "./_posts"  # where to put the exported posts
R_FDR = "./_resources"  # where to put resource files (.jpg, .png, ...)
URL = "http://localhost:41184/"


TOK = "token=" + TOK
ID_DEST = {}
DEST_ID = {}

link_not_published = []
link_false = []

# INLINE_LINK_RE = re.compile(r'\[([^\]]+)\]\(:([^)]+)\)')
INLINE_LINK_RE = re.compile(r'\[.*\]\(\:.*\)')


# find the id of the specified id
def get_tag_id(_tag, TOK, n=1):
  # get all tags from joplin
  tags = json.loads(
      subprocess.Popen("curl " + URL + "tags?" + TOK + "&page=" + str(n),
                       stdout=subprocess.PIPE).stdout.read())

  # compare tags' title
  for i in tags['items']:
    if i['title'] == _tag:
      return i['id']

  # continue find in next page or return no (not found)
  if tags['has_more']:
    return get_tag_id(_tag, TOK, n + 1)
  else:
    return None


# check id and destination, add them into dictionaries
def check_add_dict(id, dest):
  # check if id-dest exists, if conflict to dicts
  if id in ID_DEST.keys():
    if ID_DEST[id] == dest:
      return True
    else:
      return False
  if dest in DEST_ID.keys():
    if DEST_ID[dest] == id:
      return True
    else:
      return False

  # add id-dest pair
  ID_DEST[id] = dest
  DEST_ID[dest] = id

  return True



def travel_tag_notes(tag_id, TOK, n=1):
  #. get all notes with PUBTAG
  notes = json.loads(
      subprocess.Popen(
          "curl " + URL + "tags/" + tag_id + "/notes?" + TOK +
          "&fields=id,parent_id,title,user_created_time,user_updated_time,body"
          + "&limit=100&page=" + str(n),
          stdout=subprocess.PIPE).stdout.read())


  #. for each note
  for note in notes['items']:
    note_id = note['id']

    note_tags = json.loads(
        subprocess.Popen("curl " + URL + "notes/" + note_id + "/tags?" + TOK +
                         "&limit=100",
                         stdout=subprocess.PIPE).stdout.read())
    #^ a note shouldn't have more than 100 tags ...
    note['tags'] = [ii['title'] for ii in note_tags['items']]
    note['tags'].remove(PUBTAG)
    tag_line = "tags: [" + ", ".join(x for x in note['tags']) +"]"

    note_dest = ID_DEST[note_id]
    doc = note['body']

    # last_modified_at: 2016-03-09T16:20:02-05:00
    last_modified_line = "last_modified_at: " + datetime.datetime.fromtimestamp(
        int(note['user_updated_time']) / 1000).strftime('%Y-%m-%dT%H:%M:%S+08:00')
    #^ for minimal mistake theme show information
    last_updated_line = "last_updated: " + datetime.datetime.fromtimestamp(
        int(note['user_updated_time']) / 1000).strftime('%Y-%m-%dT%H:%M:%S+08:00')
    #^ for jekyll sort post


    # convert resource link
    #! this must be done before convert markdown link
    #  because the resouce list is reported by joplin api
    #  deal it first, then my own code don't have to distinguish them
    #  why distinguish resource and markdown link?
    #    for resource, we only copy it
    #    for markdown, we need to generate it
    res = json.loads(
        subprocess.Popen("curl " + URL + "notes/" + note_id + "/resources?" +
                         TOK + "&fields=id,file_extension&limit=100",
                         stdout=subprocess.PIPE).stdout.read())
    #^ currently, only convert 100 resources
    for i in res['items']:
      id = i['id']
      ori_str = ':/' + id
      res_dest = ID_DEST[id]
      new_link_url = os.path.relpath(res_dest, N_FDR)
      doc = doc.replace(ori_str, new_link_url)




    # convert markdown link
    #! note: this use simple pattern to find markdown links
    in_links = INLINE_LINK_RE.findall(doc)
    for link in in_links:
      s = link.rfind("/")
      link_id = link[s+1:-1]

      # deal if the link is not published or invalid
      if not link_id in ID_DEST.keys():
        try:
          #. if the link is a no published note ...
          ex_note = json.loads(
              subprocess.Popen("curl " + URL + "notes/" + link_id + "?" + TOK +
                               "&fields=title,source_url",
                               stdout=subprocess.PIPE).stdout.read())["title"]
          ex_note = "[" + ex_note + "] linked in [" + note['title'] + "]"
          link_not_published.append(ex_note)
          doc = doc.replace(link[s - 2:],
                            ' <- "not ready yet, maybe come here later" ')
          # maybe use source_url?
        except:
          #. if the link is invalid (maybe sample in code block)
          link_false.append("fake link [" + link_id + "] shown in [" + note['title'] + "]")
          print('seems invalid markdown link\n')
          # maybe use source_url?
        continue


      link_dest = ID_DEST[link_id]
      new_link_url = os.path.relpath(link_dest, N_FDR)
      new_link = link[0:s-1]+new_link_url+')'

      doc = doc.replace(link, new_link)

    yaml_head = "---\n"
    yaml_head += tag_line + "\n"
    yaml_head += last_modified_line +  "\n"
    yaml_head += last_updated_line +  "\n"
    yaml_head += "---\n"

    f = open(note_dest, "w",encoding="utf-8")
    f.write(yaml_head)
    f.write(doc)
    f.close()

  if notes['has_more']:
    return travel_tag_notes(tag_id, TOK, n+1)
  else:
    return True









def add_resource(note_id, TOK, n=1):
  #. get resource list
  res = json.loads(
      subprocess.Popen("curl " + URL + "notes/" + note_id + "/resources?" +
                       TOK + "&fields=id,file_extension&limit=100",
                       stdout=subprocess.PIPE).stdout.read())

  for i in res['items']:
    #. get id
    id = i['id']

    #. get dest
    new_fname = id + '.' + i['file_extension']
    res_dest = os.path.join(R_FDR, new_fname)

    #. copy resource
    subprocess.Popen("curl -o " + res_dest + " " + URL + "resources/" + id +
                     "/file?" + TOK,
                     stdout=subprocess.PIPE).stdout.read()

    #. id-dest dictionary creation
    o = check_add_dict(id, res_dest)
    if not o:
      return False

  if res['has_more']:
    return add_resource(id, TOK, n+1)
  else:
    return True


# generate id(note)-dest dictionary
# dest is timebased
def travel_tag_notes_pre(tag_id, TOK, n=1):
  #. get notes with PUBID
  notes = json.loads(
      subprocess.Popen(
          "curl " + URL + "tags/" + tag_id + "/notes?" + TOK +
          "&fields=id,parent_id,title,user_created_time,user_updated_time,body",
          stdout=subprocess.PIPE).stdout.read())

  for note in notes['items']:
    #. id
    note_id = note['id']

    #. dest
    time_str = datetime.datetime.fromtimestamp(
        int(note['user_created_time']) / 1000).strftime('%Y-%m-%d')
    new_fname = time_str + '-' + str(note['user_created_time']) + ".md"
    note_dest = os.path.join(N_FDR, new_fname)

    #. note_id-dest dictionary creation
    o = check_add_dict(note_id, note_dest)
    if not o:
      return False

    #. also add resource-dest into dictionary
    o = add_resource(note_id, TOK)
    if not o:
      return False


  if notes['has_more']:
    return travel_tag_notes_pre(tag_id, TOK, n+1)
  else:
    return True




def main():

  # 1. get publication tag's id
  PUBTAGID = get_tag_id(PUBTAG, TOK, n=1)
  if PUBTAGID is None:
    print ("\n\n\nno note has tag: ", PUBTAG)
    return

  # 2. see all notes with pubtag, generate id-dest dictionary
  ret = travel_tag_notes_pre(PUBTAGID, TOK)
  if not ret:
    print("\n\n\nsome thing wrong: maybe duplicate id\n\n")

  # 3. create output folders
  os.makedirs(N_FDR, exist_ok=True)
  os.makedirs(R_FDR, exist_ok=True)

  # 4. extract notes and resources
  travel_tag_notes(PUBTAGID, TOK)

  print(*link_not_published, sep = "\n")
  print(*link_false, sep = "\n")

  print('done')


if __name__ == '__main__':
  main()
