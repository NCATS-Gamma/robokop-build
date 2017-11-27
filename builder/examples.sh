#Example command lines 
#All assume that greent is installed in a sibling directory to protocop.  

#Type 1 query (Disease/Gene/GeneticCondition)
#Start at Ebola, support with chemotext, chemotext2 and cdw
#Label in neo4j will be "test1"
PYTHONPATH=../../greent python builder.py -s cdw -s chemotext2 -s chemotext -q 1 --start "Ebola Virus Disease" -l test1 

#Type 2 query (Substance/Gene/Process/Cell/Anatomy/Phenotype/Disease)
#Start at PRAMIPEXOLE, end at Restless Legs Syndrom
#support with chemotext and chemotext2
#Label in neo4j will be "test2"
PYTHONPATH=../../greent python builder.py -s chemotext2 -s chemotext -q 2 --start "PRAMIPEXOLE" --end "Restless Legs Syndrome" -l test2

#Same as the above query, but not using the -q 2 shortcut
#PYTHONPATH=../../greent python builder.py -s chemotext2 -s chemotext -p "SGPCATD" --start "PRAMIPEXOLE" --end "Restless Legs Syndrome" -l test2

#Query specifying: Start at Ebola, end at a genetic condition. Link should either be direct or via one other node of any type
PYTHONPATH=../../greent python builder.py -s cdw -s chemotext2 -s chemotext -p "D(1-2)X" --start "Ebola Virus Disease" -l test3 

#Start at the Substance LISINOPRIL
#Find phenotypes that are connected to it either directly (1 edge), or via links including up to 2 other nodes (3 edges).
#Support with chemotext & chemotext2
#Label in neo4j will be test4
PYTHONPATH=../../greent python builder.py -s chemotext2 -s chemotext -p "S(1-3)T" --start "LISINOPRIL" -l test4 
