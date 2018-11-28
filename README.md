# autotag
A tool for auto tagging local image via saucenao and danbooru for linux.

The tags will be written into image's XMP metadata.

# Dependencies

* saucenao(not required to install on pip)
    * beautifulsoup4(pip)
    * requests(pip)
* python-xmp-toolkit(pip)
    * exempi(rpm,apt,yay,etc.)

# Usage

After installing dependencies, you have to register on saucenao and danbooru.

Then edit `autotag.py` to fill in the api keys as well as the directory to scan images.

Finally, run `python3 autotag.py`.

It will generate a local sqlite database  `task.db` to store the paths and status of scanned images.
Every time you run the program, it will scan the folder(*maybe recursively?*) , query on saucenao and update image metadata.

Network-caused failure will be re-queried next time you run the program.

If daily saucenao quota is run out of, it will wait for an hour to check again.

You can add it into crontab to scan the media library in a regular basis.