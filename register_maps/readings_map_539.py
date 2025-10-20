
my %getsonly539 = (  #info from belu and godmorgon
  "sFlowRate"		=> {cmd2=>"0A033B", type =>"1clean", unit =>" cl/min"},
  "sHumMaskingTime"	=> {cmd2=>"0A064F", type =>"1clean", unit =>" min"},
  "sHumThreshold"	=> {cmd2=>"0A0650", type =>"1clean", unit =>" %"},
  "sHeatingRelPower"	=> {cmd2=>"0A069A", type =>"1clean", unit =>" %"},
  "sComprRelPower"	=> {cmd2=>"0A069B", type =>"1clean", unit =>" %"},
  "sComprRotUnlimit"	=> {cmd2=>"0A069C", type =>"1clean", unit =>" Hz"},
  "sComprRotLimit"	=> {cmd2=>"0A069D", type =>"1clean", unit =>" Hz"},
  "sOutputReduction"	=> {cmd2=>"0A06A4", type =>"1clean", unit =>" %"},
  "sOutputIncrease"	=> {cmd2=>"0A06A5", type =>"1clean", unit =>" %"},
  "sHumProtection"	=> {cmd2=>"0A09D1", type =>"1clean", unit =>""},
  "sSetHumidityMin"	=> {cmd2=>"0A09D2", type =>"1clean", unit =>" %"},
  "sSetHumidityMax"	=> {cmd2=>"0A09D3", type =>"1clean", unit =>" %"},
  "sCoolHCTotal"	=> {cmd2=>"0A0648", cmd3 =>"0A0649", type =>"1clean", unit =>" kWh"},
  "sDewPointHC1"	=> {cmd2=>"0B0264", type =>"5temp",  unit =>" °C"},
  "sDewPointHC2"	=> {cmd2=>"0C0264", type =>"5temp",  unit =>" °C"}
 );