#!/usr/bin/env python

import os, sys, re, shutil, glob
import argparse
import requests

from bs4 import BeautifulSoup
import lxml.html

if sys.version_info.major != 3:
	raise Exception("Only Python 3 plz")

URL = "https://{team_name}.slack.com/customize/emoji"
URL_DELETE = "https://{team_name}.slack.com/api/emoji.remove"


def _session(args):
	assert args.cookie, "Cookie required"
	assert args.team_name, "Team name required"
	session = requests.session()
	session.headers = {'Cookie': args.cookie}
	session.url = URL.format(team_name=args.team_name)
	session.url_delete = URL_DELETE.format(team_name=args.team_name)
	return session


def _argparse():
	parser = argparse.ArgumentParser(
		description='Bulk upload/export/delete of emoji to/from slack'
	)
	parser.add_argument(
		'--team-name', '-t',
		default=os.getenv('SLACK_TEAM'),
		help='Defaults to the $SLACK_TEAM environment variable.'
	)
	parser.add_argument(
		'--cookie', '-c',
		default=os.getenv('SLACK_COOKIE'),
		help='Defaults to the $SLACK_COOKIE environment variable.'
	)
	parser.add_argument(
		'--prefix', '-p',
		default=os.getenv('EMOJI_NAME_PREFIX', ''),
		help='Prefix to add to generated emoji name. '
		'Defaults to the $EMOJI_NAME_PREFIX environment variable.'
	)
	parser.add_argument(
		'--suffix', '-s',
		default=os.getenv('EMOJI_NAME_SUFFIX', ''),
		help='Suffix to add to generated emoji name. '
		'Defaults to the $EMOJI_NAME_SUFFIX environment variable.'
	)
	parser.add_argument(
		'--export', '-e', action='store_true',
		help="Exports emoji to given folder (defaults to 'slack_emoji', takes precedence over --delete)")
	parser.add_argument(
		'--force', '-F', action='store_true',
		help="Overwrites any existing emojis")
	parser.add_argument(
		'--delete', '-d', action='store_true',
		help="Deletes emoji given (can use * as wildcard)")
	parser.add_argument(
		'files',
		nargs='*',
		help=('Names of emoji to upload/delete (may use * as wildcard), or folder to put the exported emoji in'),
	)
	args = parser.parse_args()
	if not args.team_name:
		args.team_name = input('Please enter the team name: ').strip()
	if not args.cookie:
		args.cookie = input('Please enter the "emoji" cookie: ').strip()
	
	args.directory = "slack_emoji"
	if len(args.files) > 0:
		args.directory = args.files[0]
	return args

def main():
	args = _argparse()
	session = _session(args)
	if args.export:
		export(session, args)
	elif args.delete:
		delete(session, args)
	else:
		upload(session, args)

def upload(session, args):
	existing_emoji = get_current_emoji_list(session)
	uploaded = 0
	skipped = 0

	S =[]
	for path in args.files:
		for filename in glob.glob(path):
			S.append(filename)
	print("Files: %s\n"%('; '.join(S)))
	print("Do you want to upload these %d files?"%len(S), end=' ')

	if not confirmation():
		print("Aborted")
		return

	for filename in S:
		print("Processing {}.".format(filename))
		emoji_name = '{}{}{}'.format(
			args.prefix.strip(),
			os.path.splitext(os.path.basename(filename))[0],
			args.suffix.strip()
		)
		if emoji_name in existing_emoji:
			if args.force:
				delete_emoji(session, emoji_name)
				upload_emoji(session, emoji_name, filename)
				print("{} replaced.".format(filename))
				uploaded += 1
			else:
				print("Skipping {}. Emoji already exists".format(emoji_name))
				skipped += 1
		else:
			upload_emoji(session, emoji_name, filename)
			print("{} uploaded.".format(filename))
			uploaded += 1
	print('\nUploaded {} emoji. ({} already existed)'.format(uploaded, skipped))


def export(session, args):
	if not os.path.exists(args.directory):
		os.makedirs(args.directory)

	resp = session.get(session.url)
	tree = lxml.html.fromstring(resp.text)
	urls = tree.xpath(r'//td[@headers="custom_emoji_image"]/span/@data-original')
	names = [u.split('/')[-2] for u in urls]

	for emoji_name, emoji_url in zip(names, urls):
		if "alias" not in emoji_url:  # this does not seem necessary ...
			file_extension = emoji_url.split(".")[-1]
			request = session.get(emoji_url, stream=True)
			if request.status_code == 200:
				filename = '%s/%s.%s' % (args.directory, emoji_name,
										 file_extension)
				with open(filename, 'wb') as out_file:
					shutil.copyfileobj(request.raw, out_file)
				del request


def delete(session, args):
	existing_emoji = get_current_emoji_list(session)
	deleted = 0

	S =[]
	for path in args.files:
		patt = re.compile(re.escape(path).replace(r"\*", ".*")+"$")
		for emoji in existing_emoji:
			if patt.match(emoji):
				S.append(emoji)

	if len(S) == 0:
		print("No emoji matched the given names. Aborting...")
		return 

	print("Emoji to delete: %s\n"%('; '.join(S)))
	print("Do you want to delete these %d emoji?"%len(S), end=' ')

	if not confirmation():
		print("Aborted")
		return

	for emoji in S:
		print("Processing {}.".format(emoji))

		if delete_emoji(session, emoji):
			deleted += 1
			print("{} deleted.".format(emoji))
		else:
			print("Error while deleting {}.".format(emoji))
	print('\nDeleted {} emoji. ({} failed)'.format(deleted, len(S)-deleted))






def get_current_emoji_list(session):
	r = session.get(session.url)
	r.raise_for_status()
	x = re.findall("data-emoji-name=\"(.*?)\"", r.text)
	return x


def upload_emoji(session, emoji_name, filename):
	# Fetch the form first, to generate a crumb.
	r = session.get(session.url)
	r.raise_for_status()
	soup = BeautifulSoup(r.text, "html.parser")
	crumb = soup.find("input", attrs={"name": "crumb"})["value"]

	data = {
		'add': 1,
		'crumb': crumb,
		'name': emoji_name,
		'mode': 'data',
	}
	files = {'img': open(filename, 'rb')}
	r = session.post(session.url, data=data, files=files, allow_redirects=False)
	r.raise_for_status()
	# Slack returns 200 OK even if upload fails, so check for status of 'alert_error' info box
	if b'alert_error' in r.content:
		soup = BeautifulSoup(r.text, "html.parser")
		crumb = soup.find("p", attrs={"class": "alert_error"})
		print("Error with uploading %s: %s" % (emoji_name, crumb.text))

def delete_emoji(session, emoji_name):
	data = {
		'name': emoji_name,
		'token': "xoxs-195008312805-195741066343-195722307958-36ca7f8642",
		'set_active': "true",
	}
	r = session.post(session.url_delete, data=data, allow_redirects=False)
	r.raise_for_status()

	# @Temporary: Check JSON and print error, if exists
	if b"error" in r.content:
		print(r.content)
		return False
	return True

def confirmation(deft=True):
	a = input()
	if len(a) == 0:
		return deft
	else:
		return a.lower() in ("y","yes")

if __name__ == '__main__':
	main()
