my %sets539only =(
  "p75passiveCooling"		=> {cmd2=>"0A0575", argMin =>   "0",	argMax =>  "4",		type =>"1clean", unit =>""},    
  "p99PumpRateHC"		=> {cmd2=>"0A02CB", argMin =>   "0",	argMax =>  "100",	type =>"5temp",  unit =>" %"},  
  "p99PumpRateDHW"		=> {cmd2=>"0A02CC", argMin =>   "0",	argMax =>  "100",	type =>"5temp",  unit =>" %"} ,
  "p99CoolingHC1Switch"		=> {cmd2=>"0B0287", argMin =>   "0",	argMax =>  "1",		type =>"1clean", unit =>""},
  "p99CoolingHC1SetTemp"	=> {cmd2=>"0B0582", argMin =>  "12",	argMax =>  "27",	type =>"5temp",  unit =>" °C"},    #suggested by TheTrumpeter
  "p99CoolingHC1HysterFlowTemp"	=> {cmd2=>"0B0583", argMin =>  "0.5",	argMax =>  "5",		type =>"5temp",  unit =>" K"}, #suggested by TheTrumpeter
  "p99CoolingHC1HysterRoomTemp"	=> {cmd2=>"0B0584", argMin =>  "0.5",	argMax =>  "3",		type =>"5temp",  unit =>" K"},  #suggested by TheTrumpeter
  "p99CoolingHC2Switch"		=> {cmd2=>"0C0287", argMin =>   "0",	argMax =>  "1",		type =>"1clean", unit =>""},     #suggested by rett_de
  "p99CoolingHC2SetTemp"	=> {cmd2=>"0C0582", argMin =>  "12",	argMax =>  "27",	type =>"5temp",  unit =>" °C"},    #suggested by rett_de
  "p99CoolingHC2HysterFlowTemp"	=> {cmd2=>"0C0583", argMin =>  "0.5",	argMax =>  "5",		type =>"5temp",  unit =>" K"}, #suggested by rett_de
  "p99CoolingHC2HysterRoomTemp"	=> {cmd2=>"0C0584", argMin =>  "0.5",	argMax =>  "3",		type =>"5temp",  unit =>" K"}  #suggested by Trett_de
);