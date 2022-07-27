import os
import sys

import pexpect

os.chdir("./cocoapods-downloader")
process = pexpect.spawn('ruby ' + sys.argv[1])
process.expect(['sername', pexpect.EOF, pexpect.TIMEOUT])
process.sendline('')
process.expect(['assword', pexpect.EOF, pexpect.TIMEOUT])
process.sendline('')

