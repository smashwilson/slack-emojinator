# Slack Emojinator

*Bulk upload emoji into Slack*

Want to create a custom Slack emoji for every pokemon? Slack doesn't currently expose an API endpoint for creating emoji, probably to prevent users from doing exactly what I'm doing, but here's a way to do it anyway.

## Creating Emoji

You'll need Python and `pip` to get started. I recommend using [pipenv](https://docs.pipenv.org/).

Prepare a directory that contains an image for each emoji you want to create. Remember to respect Slack's specifications for valid emoji images: no greater than 128px in width or height, no greater than 64K in image size. The base filename of each image file should be the name of the emoji (the bit you'll type inside `:` to display it).

Clone the project and install its prereqs:

`libxml` is required on your system, if you'd like to use the bulk export script.

```bash
git clone https://github.com/smashwilson/slack-emojinator.git
cd slack-emojinator
pipenv install
```

You'll need to provide your team name (the bit before ".slack.com" in your admin URL) and your session cookie (grab it from your browser). Copy `.env.example`, fill them in, and source it.

To grab your Slack session cookie:

* [Open your browser's dev tools](http://webmasters.stackexchange.com/a/77337) and copy the value of `document.cookie`.
* Go to the Network tab.
* Re-load your workspace's `https://{teamname}.slack.com/customize/emoji` page.
* Find the call to `emoji` (it is most likely the very top request).
* Scroll to `Request-Headers`, copy the value of "Cookie," and add to your `.env` file.

```bash
cp .env.example .env
${EDITOR} .env
source .env
```

Now you're ready to go. Use a shell glob to invoke `upload.py` with the emoji files as ARGV:

```bash
pipenv run python upload.py ${EMOJI_DIR}/*.png
```

:sparkles:

## Exporting Emoji

To export emoji, use `export.py` and specify an emoji directory:

```bash
source .env
pipenv run python export.py path-to-destination/
```
