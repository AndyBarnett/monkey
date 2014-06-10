monkey (also known as 'typewriter')
======

Just put all these files in the same folder on a linux box and they'll all work, providing you set up the cron job as below:

Cron Job:
======
00 18 * * 1-5 cd ~/typewriter && { ./typewriter > log/typewriter.stdout 2> log/typewriter.stderr; }
30 09 * * 1-5 cd ~/typewriter && { ./killmonkey > log/killmonkey.stdout 2> log/killmonkey.stderr & sleep 30; ./autoReportWithReopening.py config.ini "$(cat latest)" > log/autoreport.stdout 2> log/autoreport.stderr; }
