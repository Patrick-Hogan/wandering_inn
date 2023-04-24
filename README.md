# wandering_inn

**NOTE: It looks like wanderinginn.com has changed firewall settings to prevent/limit scraping;
attempting to scrape an entire volume--much less multiple volumes--will likely result in a ban on
your IP.**

I've re-checked the site for any prohibition on scraping and don't see any. I'm not sure what the
actual threshold to trigger a ban is (best guess: a sustained high rate of access over a short
period of time; I was banned with ~100 page accesses in a day, but the last 90 or so of those were
in rapid succession via script). 

I recommend against using any options other than "--chapter" to select content. 

Download and convert [The Wandering Inn](https://wanderinginn.com/) to epub and mobi (kindle) format

I have no affiliation with and no rights to The Wandering Inn; I'm just a fan who likes to read on
my kindle and on my phone even when I don't have internet access. 

The created ebook sometimes has some rough patches to it; I'd encourage you to buy the [official
releases](https://www.amazon.com/pirate-aba/e/B07XCYVYMW?ref=dbs_mng_calw_a_0)
as they happen on Amazon to get a polished copy and [support the
author](https://www.patreon.com/user?u=4240617). I only created this project so I can catch/keep up
with the web publications.

This script relies on [ebookmaker](https://github.com/setanta/ebookmaker) and its dependencies, and
runs on python3. Converting to mobi format also relies on calibre, and the script is written for
bash.

# Usage

1) Clone this repository:

```bash
git clone --recurse-submodules https://github.com/Patrick-Hogan/wandering_inn.git
cd wandering_inn
```

2) Install requirements
   
      Recommended: install requirements in a [virtual
      environment](https://docs.python.org/3/library/venv.html).
      ```bash
      # in a virtual environment:
      pip install -r requirements.txt

      # Alternatively, use the --user flag to avoid needing sudo/admin:
      pip install --user -r requirements.txt
      ```

3) Run the script: 

    Options can be displayed by passing `-h` or `--help`:

    ```bash
    ./wanderinginn2epub.py --help
    ```

    Generate a single epub for all available public chapters:

    ```bash
    ./wanderinginn2epub.py
    ```

    Pretty print the chapters that would be included:

    ```bash
    ./wanderinginn2epub.py --output-print-index
    ```

    Generate one epub per volume for volumes 1-7:
    ```bash
    ./wanderinginn2epub.py --volume 1 2 3 4 5 6 7 --output-by-volume
    ```

    Generate one epub per chapter for volume 8, stripping color so light fonts are readable on
    black-and-white screens (e.g., winter sprites' coversations):
    ```bash
    ./wanderinginn2epub.py --volume 8 --output-by-chapter --strip-color
    ```

    Generate an epub for the latest published chapter only:
    ```bash
    ./wanderinginn2epub.py --chapter latest --output-by-chapter
    ```

# Automated Mailing

I have never set up automated mailing from a windows box and have no interest in doing so;
configuration on linux varies, but the following setup works on ubuntu 18.10+ for me.

To automatically email to amazon devices, I use msmtp and mutt, configured to use my gmail account
to send mail; any backend mail configuration can be used, though, as long as the account is added to
the approved addresses in your amazon account. Once your configuration is set up to allow mutt to
send mail from the command line, you can specify the list of recipients (e.g., the device addresses
from your amazon account) in an environment variable, from the command line or in a recipients.txt
(space or newline separated). 

