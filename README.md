# Slack Emojinator

*Bulk upload emoji into Slack*

Want to create a custom Slack emoji for every pokemon? Slack doesn't currently expose an API endpoint for creating emoji, probably to prevent users from doing exactly what I'm doing, but here's a way to do it anyway.

## Creating Emoji

You'll need Python and `pip` to get started. I recommend using [virtualenv](https://virtualenv.pypa.io/en/latest/) and possibly [virtualenvwrapper](https://virtualenvwrapper.readthedocs.org/en/latest/) as well. Standard best-practice Python stuff.

Prepare a directory that contains an image for each emoji you want to create. Remember to respect Slack's specifications for valid emoji images: no greater than 128px in width or height, no greater than 64K in image size. The base filename of each image file should be the name of the emoji (the bit you'll type inside `:` to display it).

Clone the project, create a new virtualenv, and install the prereqs:

```bash
git clone https://github.com/smashwilson/slack-emojinator.git
cd slack-emojinator
mkvirtualenv slack-emojinator
pip install -r requirements.txt
```

Now you're ready to go. Use a shell glob to invoke `upload.py` with the emoji files as ARGV:

```bash
python upload.py ${EMOJI_DIR}/*.png
```

:sparkles:
