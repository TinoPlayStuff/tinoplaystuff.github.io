#!/usr/bin/python3
import sys, glob, os, subprocess, json
from pathlib import Path
import datetime, re


PUBTAG = "published"
URL = "http://localhost:41184/"
TOK = "token=4ccabec736a39dcfeac27efc8ab253ca4760c7aeb2bd468b5932e2e2c181b08557a507081f88fb0a80efb66650fc09b9fde7c4202f437cf73b79c18c55e0456a"
# TOK = "token=4444503f811297abb7e0819eb3b32c33a3c7542a50325233ea6eff9889b4315bc437621aca8b90221b553d3bb0358a4d6e4b3225849d483c87394d18df38bf1e"
N_FDR = "./_posts"
R_FDR = "./_resources"
ID_DEST = {}
DEST_ID = {}

# INLINE_LINK_RE = re.compile(r'\[([^\]]+)\]\(:([^)]+)\)')
INLINE_LINK_RE = re.compile(r'\[.*\]\(\:.*\)')

def get_tag_id(id_str, TOK, n=1):
  dd = json.loads(
      subprocess.Popen("curl http://localhost:41184/tags?" + TOK + "&pages=" +
                       str(n),
                       stdout=subprocess.PIPE).stdout.read())
  # print(dd['items'][0]['title'])

  for i in dd['items']:
    # print(i['title'])
    if i['title'] == id_str:
      return i['id']

  # not found in these page

  if dd['has_more']:
    tag_id = get_tag_id(id_str, TOK, n + 1)
    if not tag_id == 'no':
      return tag_id
  else:
    return 'no'


def check_add_dict(id, dest):
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

  ID_DEST[id] = dest
  DEST_ID[dest] = id

  return True


def travel_tag_notes(tag_id, TOK, n=1):

  notes = json.loads(
      subprocess.Popen(
          "curl http://localhost:41184/tags/" + tag_id + "/notes?" + TOK +
          "&fields=id,parent_id,title,user_created_time,user_updated_time,body",
          stdout=subprocess.PIPE).stdout.read())

  for note in notes['items']:
    note_id = note['id']
    note_tags = json.loads(
        subprocess.Popen("curl http://localhost:41184/notes/" + note_id +
                         "/tags?" + TOK + "&limits=100",
                         stdout=subprocess.PIPE).stdout.read())
    # a note shouldn't have more than 100 tags

    note['tags'] = [ii['title'] for ii in note_tags['items']]
    note['tags'].remove(PUBTAG)
    
    tag_line = "tags: [" + ", ".join(x for x in note['tags']) +"]"

    note_dest = ID_DEST[note_id]
    doc = note['body']

    # last_modified_at: 2016-03-09T16:20:02-05:00
    update_date_line = "last_modified_at: " + datetime.datetime.fromtimestamp(
        int(note['user_updated_time']) / 1000).strftime('%Y-%m-%dT%H:%M:%S+08:00')


    # convert resource link
    res = json.loads(
      subprocess.Popen(
          "curl http://localhost:41184/notes/" + note_id + "/resources?" + TOK +
          "&fields=id,file_extension&limits=100",
          stdout=subprocess.PIPE).stdout.read())
    for i in res['items']:
      id = i['id']
      ori_str = ':/'+id
      res_dest = ID_DEST[id]
      new_link_url = os.path.relpath(res_dest, N_FDR)
      doc = doc.replace(ori_str, new_link_url)




    # convert markdown link
    in_links = INLINE_LINK_RE.findall(doc)
    for link in in_links:
      s = link.rfind("/")
      link_id = link[s+1:-1]
      if not link_id in ID_DEST.keys():
        continue
      
      res_dest = ID_DEST[link_id]

      new_link_url = os.path.relpath(res_dest, N_FDR)
      new_link = link[0:s-1]+new_link_url+')'

      doc = doc.replace(link, new_link)

      # print(res_dest)



    
    
    yaml_head = "---\n"
    yaml_head += tag_line + "\n"
    yaml_head += update_date_line +  "\n"
    yaml_head += "---\n"

    f = open(note_dest, "w",encoding="utf-8")
    f.write(yaml_head)
    f.write(doc)
    f.close()


    






def add_resource(note_id, TOK, n=1):
  #/notes/:id/resources
  res = json.loads(
      subprocess.Popen(
          "curl http://localhost:41184/notes/" + note_id + "/resources?" + TOK +
          "&fields=id,file_extension&limits=100",
          stdout=subprocess.PIPE).stdout.read())
  for i in res['items']:
    id = i['id']

    new_fname = id + '.' + i['file_extension']

    res_dest = os.path.join(R_FDR, new_fname)

    # /resources/:id/file
    subprocess.Popen(
          "curl -o " +  res_dest + " http://localhost:41184/resources/" + id + "/file?" + TOK,
          stdout=subprocess.PIPE).stdout.read()

    o = check_add_dict(id, res_dest)
    if not o:
      return False

    

  if res['has_more']:
    return add_resource(id, TOK, n+1)
  else:
    return True



def travel_tag_notes_pre(tag_id, TOK, n=1):

  notes = json.loads(
      subprocess.Popen(
          "curl http://localhost:41184/tags/" + tag_id + "/notes?" + TOK +
          "&fields=id,parent_id,title,user_created_time,user_updated_time,body",
          stdout=subprocess.PIPE).stdout.read())

  for i in notes['items']:
    note_id = i['id']

    time_str = datetime.datetime.fromtimestamp(
        int(i['user_created_time']) / 1000).strftime('%Y-%m-%d')
    new_fname = time_str + '-' + str(i['user_created_time']) + ".md"

    note_dest = os.path.join(N_FDR, new_fname)

    o = check_add_dict(note_id, note_dest)
    if not o:
      return False

    o = add_resource(note_id, TOK)
    if not o:
      return False


  if notes['has_more']:
    return travel_tag_notes_pre(tag_id, TOK, n+1)
  else:
    return True




def main():
  # dd = os.popen("curl " + URL + "search?query=yolo&" + TOK).read()
  # dd = os.popen('curl http://localhost:41184/notes/search?token=4ccabec736a39dcfeac27efc8ab253ca4760c7aeb2bd468b5932e2e2c181b08557a507081f88fb0a80efb66650fc09b9fde7c4202f437cf73b79c18c55e0456a&query=yolo').read()

  PUBTAGID = get_tag_id(PUBTAG, TOK, n=1)
  # dd = subprocess.Popen("curl http://localhost:41184/tags?" + TOK, stdout=subprocess.PIPE).stdout.read()
  # ddj = json.loads(dd)
  # print(dd)

  o = travel_tag_notes_pre(PUBTAGID, TOK)
  if not o:
    print("\n\n\nsome thing wrong: maybe duplicate id\n\n")
  # dd = subprocess.Popen("curl http://localhost:41184/tags/" + PUBTAGID + "/notes?token=4ccabec736a39dcfeac27efc8ab253ca4760c7aeb2bd468b5932e2e2c181b08557a507081f88fb0a80efb66650fc09b9fde7c4202f437cf73b79c18c55e0456a", stdout=subprocess.PIPE).stdout.read()
  # print("\n\n\n", dd)

  os.makedirs(N_FDR, exist_ok=True)
  os.makedirs(R_FDR, exist_ok=True)

  travel_tag_notes(PUBTAGID, TOK)

  print('done')


if __name__ == '__main__':
  main()
