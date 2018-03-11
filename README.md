# git-dropshare

`git-dropshare` use Dropbox to store, and track binary files.
Using the sharing fonctionality of Dropbox, it is then possible to use any Git service you like for collaborative development, while taking advantage of a free Dropbox account to store big files, LFS likewise.

## Requirements

* A recent Python distribution (developed with 3.6)
* A Dropbox account

## Installation procedure

1. Install dropshare from GitHub (pip3 installation to come).
2. Go to Dropbox developpers interface, and get a token for the **full Dropbox**.
3. Choose a folder inside Dropbox, which is going to serve for storage.
4. Within any Git valid repository, run `git ds init` and answer few questions:
   - a `account` label for representing your Storage area inside your Dropbox;
   - a short `description` for the storage area;
   - the relative path for this storage, within your Dropbox;
   - and the `global token` got at step 1.

The Dropshare installation can be ckecked with command: `git ds check`.

Decide which files patterns (follow `fnmatch(3)`  manual for details) should be handled by Dropshare.
For each `pattern`, run `git ds track <pattern>`. The local file `.gitattributes` will be edited accordingly.

For example:

    git ds track '*.pdf'

adds the line `*.pdf filter=dropshare` to .gitattributes, if not already present.

**N.B.** In case this is a team development, **everybody** must agree on the content of the file `.gitattributes`!

**N.B.** If sharing is considered, be warned this is incompatible with Dropbox *Applications* model.

## Typical use

When **checking** files:

    git add file.pdf
    git commit file.pdf "my first binary file"
    git push
    git ds push

To **checkout** repository:

    git pull
    git ds pull

Notice, there is NO requirement, as far as Git is concerned, to pull files outside the Storage area.
If `git ds pull` is not trggered, every filtered files will be seen as a *stub* which content is:

    dropshare
    file path # merely for information purpose
    hexdigest # hash content, using Dropbox algorithm

