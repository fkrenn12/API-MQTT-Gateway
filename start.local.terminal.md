# How do get it running
## Local Windows 
cd api   
uvicorn --reload main:app --port 5600 --log-level debug  
## Local Docker on Windows  
execute script: rebuild_and_start.local.development.ps1  
## Production on Linux Server
execute script: rebuild_and_start.prod.sh


