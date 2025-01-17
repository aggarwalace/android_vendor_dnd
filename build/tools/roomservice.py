#!/usr/bin/env python
# Copyright (C) 2012-2013, The CyanogenMod Project
#           (C) 2017,      The LineageOS Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import print_function

import base64
import json
import netrc
import os
import re
import sys
try:
  # For python3
  import urllib.error
  import urllib.parse
  import urllib.request
except ImportError:
  # For python2
  import imp
  import urllib2
  import urlparse
  urllib = imp.new_module('urllib')
  urllib.error = urllib2
  urllib.parse = urlparse
  urllib.request = urllib2

from xml.etree import ElementTree

product = sys.argv[1]

if len(sys.argv) > 2:
    depsonly = sys.argv[2]
else:
    depsonly = None

try:
    device = product[product.index("_") + 1:]
except:
    device = product

if not depsonly:
    print("Device %s not found. Attempting to retrieve device repository from DarkNess reDefined Github (http://github.com/DarkNess-reDefined)." % device)

repositories = []

page = 1
while not depsonly:
    result = json.loads(urllib.request.urlopen("https://api.github.com/users/DarkNess-reDefined/repos?page=%d" % page).read().decode())
    if len(result) == 0:
        break
    for res in result:
        repositories.append(res)
    page = page + 1

local_manifests = r'.repo/local_manifests'
if not os.path.exists(local_manifests): os.makedirs(local_manifests)

def exists_in_tree(lm, repository):
    for child in lm.getchildren():
        if child.attrib['path'].endswith(repository):
            return child
    return None

def exists_in_tree_device(lm, repository):
    for child in lm.getchildren():
        if child.attrib['name'].endswith(repository):
            return child
    return None

# in-place prettyprint formatter
def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def get_from_manifest(devicename):
    try:
        lm = ElementTree.parse(".repo/local_manifests/redefined_manifest.xml")
        lm = lm.getroot()
    except:
        lm = ElementTree.Element("manifest")

    for localpath in lm.findall("project"):
        if re.search("device_.*_%s$" % device, localpath.get("name")):
            return localpath.get("path")

    # Devices originally from AOSP are in the main manifest...
    try:
        mm = ElementTree.parse(".repo/manifest.xml")
        mm = mm.getroot()
    except:
        mm = ElementTree.Element("manifest")

    for localpath in mm.findall("project"):
        if re.search("device_.*_%s$" % device, localpath.get("name")):
            return localpath.get("path")

    return None

def is_in_manifest(projectname, branch):
    try:
        lm = ElementTree.parse(".repo/local_manifests/redefined_manifest.xml")
        lm = lm.getroot()
    except:
        lm = ElementTree.Element("manifest")

    for localpath in lm.findall("project"):
        if localpath.get("name") == projectname and localpath.get("revision") == branch:
            return 1

    return None

def add_to_manifest_dependencies(repositories):
    try:
        lm = ElementTree.parse(".repo/local_manifests/redefined_manifest.xml")
        lm = lm.getroot()
    except:
        lm = ElementTree.Element("manifest")

    for repository in repositories:
        repo_name = repository['repository']
        repo_target = repository['target_path']
        existing_project = exists_in_tree(lm, repo_target)
        if existing_project != None:
            if existing_project.attrib['name'] != repository['repository']:
                print ('Updating dependency %s' % (repo_name))
                existing_project.set('name', repository['repository'])
            if existing_project.attrib['revision'] == repository['branch']:
                print ('DarkNess-reDefined/%s already exists' % (repo_name))
            else:
                print ('updating branch for %s to %s' % (repo_name, repository['branch']))
                existing_project.set('revision', repository['branch'])
            continue

        print ('Adding dependency: %s -> %s' % (repo_name, repo_target))
        project = ElementTree.Element("project", attrib = { "path": repo_target,
            "remote": "github", "name": repo_name, "revision": "n" })

        if 'branch' in repository:
            project.set('revision',repository['branch'])

        lm.append(project)

    indent(lm, 0)
    raw_xml = ElementTree.tostring(lm).decode()
    raw_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + raw_xml

    f = open('.repo/local_manifests/redefined_manifest.xml', 'w')
    f.write(raw_xml)
    f.close()

def add_to_manifest(repositories):
    try:
        lm = ElementTree.parse(".repo/local_manifests/redefined_manifest.xml")
        lm = lm.getroot()
    except:
        lm = ElementTree.Element("manifest")

    for repository in repositories:
        repo_name = repository['repository']
        repo_target = repository['target_path']
        if exists_in_tree(lm, repo_name):
            print('DarkNess-reDefined/%s already exists' % (repo_name))
            continue

        print('Adding dependency: DarkNess-reDefined/%s -> %s' % (repo_name, repo_target))
        project = ElementTree.Element("project", attrib = { "path": repo_target,
            "remote": "github", "name": "DarkNess-reDefined/%s" % repo_name, "revision": "n" })

        if 'branch' in repository:
            project.set('revision',repository['branch'])
        elif fallback_branch:
            print("Using fallback branch %s for %s" % (fallback_branch, repo_name))
            project.set('revision', fallback_branch)
        else:
            print("Using default branch for %s" % repo_name)

        lm.append(project)

    indent(lm, 0)
    raw_xml = ElementTree.tostring(lm).decode()
    raw_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + raw_xml

    f = open('.repo/local_manifests/redefined_manifest.xml', 'w')
    f.write(raw_xml)
    f.close()

def fetch_dependencies(repo_path, fallback_branch = None):
    print('Looking for dependencies')
    dependencies_path = repo_path + '/dnd.dependencies'
    syncable_repos = []

    if os.path.exists(dependencies_path):
        dependencies_file = open(dependencies_path, 'r')
        dependencies = json.loads(dependencies_file.read())
        fetch_list = []

        for dependency in dependencies:
            if not is_in_manifest("%s" % dependency['repository'], "%s" % dependency['branch']):
                fetch_list.append(dependency)
                syncable_repos.append(dependency['target_path'])

        dependencies_file.close()

        if len(fetch_list) > 0:
            print('Adding dependencies to manifest')
            add_to_manifest_dependencies(fetch_list)
    else:
        print('Dependencies file not found, bailing out.')

    if len(syncable_repos) > 0:
        print('Syncing dependencies')
        os.system('repo sync --force-sync %s' % ' '.join(syncable_repos))

    for deprepo in syncable_repos:
        fetch_dependencies(deprepo)

def has_branch(branches, revision):
    return revision in [branch['name'] for branch in branches]


if depsonly:
    repo_path = get_from_manifest(device)
    if repo_path:
        fetch_dependencies(repo_path)
    else:
        print("Trying dependencies-only mode on a non-existing device tree?")

    sys.exit()

else:
    for repository in repositories:
        repo_name = repository['name']
        if repo_name.startswith("device_") and repo_name.endswith("_" + device):
            print("Found repository: %s" % repository['name'])

            manufacturer = repo_name.replace("device_", "").replace("_" + device, "")

            repo_path = "device/%s/%s" % (manufacturer, device)

            add_to_manifest([{'repository':repo_name,'target_path':repo_path,'branch':'n'}])

            print("Syncing repository to retrieve project.")
            os.system('repo sync --force-sync %s' % repo_path)
            print("Repository synced!")

            fetch_dependencies(repo_path)
            print("Done")
            sys.exit()

print("Repository for %s not found in the DarkNess reDefined Github repository list. If this is in error, you may need to manually add it to your local_manifests/redefined_manifest.xml." % device)

