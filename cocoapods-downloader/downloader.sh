set timeout 30
spawn "ruby " + $1
expect{
"sername" { send "\r" }
"assword:" { send "\r" }
}