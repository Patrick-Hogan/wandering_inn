# wandering_inn
Download and convert [The Wandering Inn](https://wanderinginn.com/) to epub and mobi (kindle) format

I have no affiliation with and no rights to The Wandering Inn; I'm just a fan who likes to read on my kindle and on my phone even when I don't have internet access. 

The created ebook sometimes has some rough patches to it; I'd encourage you to buy the [official releases](https://www.amazon.com/gp/product/B07YH9X7V7/?ie=UTF8&keywords=the%20wandering%20inn&qid=1577641602&ref_=sr_1_3&sr=8-3) as they happen on Amazon to get a polished copy and [support the author](https://www.patreon.com/user?u=4240617). I only created this project so I can catch/keep up with the web publications.

This script relies on [ebookmaker](https://github.com/setanta/ebookmaker) and its dependencies, and runs on python3. Converting to mobi format also relies on calibre, and the script is written for bash.

# Automated Mailing

I have never set up automated mailing from a windows box and have no interest in doing so; configuration on linux varies, but the following setup works on ubuntu 18.10+ for me.

To automatically email to amazon devices, I use msmtp and mutt, configured to use my gmail account to send mail; any backend mail configuration can be used, though, as long as the account is added to the approved addresses in your amazon account. Once your configuration is set up to allow mutt to send mail from the command line, you can specify the list of recipients (e.g., the device addresses from your amazon account) in an environment variable, from the command line or in a recipients.txt (space or newline separated). 
