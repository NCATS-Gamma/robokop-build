#PATH=$PATH:onto_cache PYTHONPATH=../../greent python builder.py -s cdw -s chemotext2 -s chemotext -q 1 --start "Ebola Virus Disease" -l test1 
#PATH=$PATH:onto_cache PYTHONPATH=../../greent python builder.py -s chemotext2 -s chemotext -q 2 --start "PRAMIPEXOLE" --end "Restless Legs Syndrome" -l test2
#PATH=$PATH:onto_cache PYTHONPATH=../../greent python builder.py -s cdw -s chemotext2 -s chemotext -p "D(1-2)X" --start "Ebola Virus Disease" -l test3 
PATH=$PATH:onto_cache PYTHONPATH=../../greent python builder.py -s chemotext2 -s chemotext -p "S(1-3)T" --start "LISINOPRIL" -l test4 
