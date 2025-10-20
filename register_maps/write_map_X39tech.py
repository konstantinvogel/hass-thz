my %setsX39technician =(
#   "zResetLast10errors"	=> {cmd2=>"D1",     argMin =>   "0",	argMax =>  "0",	type =>"0clean",  unit =>""},
   "zResetLast10errors"		=> {cmd2=>"D1",     argMin =>   "0",	argMax =>  "0",	type =>"D1last",  unit =>""},
#  "zPassiveCoolingtrigger"	=> {cmd2=>"0A0597", argMin =>   "0",	argMax =>  "50",	type =>"1clean",  unit =>""},
  "zPumpHC"			=> {cmd2=>"0A0052", argMin =>   "0",	argMax =>  "1",	type =>"0clean",  unit =>""},  
  "zPumpDHW"			=> {cmd2=>"0A0056", argMin =>   "0",	argMax =>  "1",	type =>"0clean",  unit =>""},
  "zControlValveDHW"  	 	=> {cmd2=>"0A0653", argMin =>   "0",    argMax =>  "1", type =>"1clean",  unit =>""}
 );