#VE/ICF Indian correction equation
#Apply long and short term trims to tables when in closed loop (determined when Target AFR is 14.7)
# V1.1 with decel filter by Chafik Moalem

import tlfiltersCBCM

show_plot = True

revLimitTable = context.GetTable("Rev Limit 1") #get the rev limit from the calibration itself
revIdleTable = context.GetTable ("Idle Speed") #get the idle speed
mapTable = context.GetTable("Volumetric Efficiency") #get the index values for the VE table
loadTable = context.GetTable("Main Target AFR") #get the index values for the Target AFR table

#Main Varables
closed_loop_val = 14.7 #Closed-Loop value
stft_open = 0 #On Indians, Short Term Fuel Trims go to 0 when out of closed-loop, but still have Target AFR at 14.7 in some instances.
hit_value = 5.0 #number of hits any one cell has to have to be used in weighted calculation
decel_slope = -7.0

rev_max = revLimitTable.GetZValue(0, 0) -.02; #Looks up the Rev Limit and subtracts a small amount to keep away from rev limit hits.
rev_min = revIdleTable.GetZValue(5,0)-.1; #set the min rev limit to idle speed - 100 RPM
min_load = loadTable.GetYValue(0); #Automatically sets the min_load to the lowest value in the Target AFR table
max_load = loadTable.GetYValue(15); #Automatically sets the max_load to the highest value in the Target AFR table
min_ve_map = mapTable.GetYValue(0); #Automatically sets the min_ve_map to the lowest value in the VE table
max_ve_map = mapTable.GetYValue(19)+20; #Automatically sets the max_ve_map to the highest value in the VE table and adds 20 for a buffer
displacement = mapTable.GetZValue (0,0);  #Get the engine displacement for temperature setting

if displacement >= 1800:
		engine_temp_thresh = 180
else:
		engine_temp_thresh = 170
	

#uncomment the following lines to override the above automatic routines if needed
#engine_temp_thresh = 180 #set this value so any temperature tuning will begin at values greater than this value.
#rev_max = 5.4  #uncomment this and put in the rev max if you want to manually override the automatically calculated value
#rev_min = 1.2  #uncomment this and put in the rev min if you want to manually override the automatically calculated value
#min_load = 12.00 #uncomment this and put in the min_load if you want to manually override the automatically calculated value
#max_load = 100.00 #uncomment this and put in the max_load if you want to manually override the automatically calculated value
#min_ve_map = 20.00 #uncomment this and put in the min_ve_map if you want to manually override the automatically calculated value
#max_ve_map = 105.00 #uncomment this and put in the max_ve_map if you want to manually override the automatically calculated value

error_multiplier = 1.0 # 1.00 #This number controls how aggressive corrections are. Example 1.05 = 5% (meaning corrections will be increased in aggressiveness by 5%)

#the table to be corrected.
correction_table = "Volumetric Efficiency"

#Callback passed to generate_sample_table that creates the corrected VE channel 
def calc_error_channel(fileHandle):
	requested = channels.GetChannelByName("Requested AFR", fileHandle)
	stftfront = channels.GetChannelByName("Short term fuel trim front", fileHandle)
	ltftfront = channels.GetChannelByName("Long term fuel trim front", fileHandle)
	stftrear = channels.GetChannelByName("Short term fuel trim rear", fileHandle)
	ltftrear = channels.GetChannelByName("Long term fuel trim rear", fileHandle)
	engine_temp = channels.GetChannelByName("Engine Temperature", fileHandle)
	rpm_value = channels.GetChannelByName("Engine Speed", fileHandle)
	normalized_map = channels.GetChannelByName("Normalized MAP for VE", fileHandle)
	loadrequest = channels.GetChannelByName("Load Request", fileHandle)
	twistgrip = channels.GetChannelByName("Twist Grip Position", fileHandle)
	
	#This filter removes all samples that have negative slope (used as decel filter)
	dc = tlfiltersCBCM.SlopeFilter(decel_slope)
	dc.do_filter(None, None, twistgrip.GetAllSamples())
	
	#This filter removes samples that equal the stft_open
	stftfilter = tlfiltersCBCM.BasicDeleteZFilter(stft_open)
	stftfilter.do_filter(None, None, stftfront.GetAllSamples())
	stftfilter.do_filter(None, None, stftrear.GetAllSamples())
	
	#calculate the combined factor for closed loop fuel adjustment
	
	trimFront = ((stftfront + ltftfront) / 100.0) + 1.0
	trimRear = ((stftrear + ltftrear) / 100.0) + 1.0

	trim = ((trimFront + trimRear) / 2)  * stftfront/stftfront * stftrear/stftrear
	
	for sample in trim.GetAllSamples():
		#don't tune the area at all if engine temp isn't up!
		if engine_temp.GetValueAtTime(sample.TimeMillis) >= engine_temp_thresh and rpm_value.GetValueAtTime(sample.TimeMillis) <= rev_max and rpm_value.GetValueAtTime(sample.TimeMillis) > rev_min and normalized_map.GetValueAtTime(sample.TimeMillis) >= min_ve_map and normalized_map.GetValueAtTime(sample.TimeMillis) <= max_ve_map and loadrequest.GetValueAtTime(sample.TimeMillis) >= min_load and loadrequest.GetValueAtTime(sample.TimeMillis) <= max_load: 
			requested_value = requested.GetValueAtTime(sample.TimeMillis)
			if requested_value == closed_loop_val:
				#do nothing, we're in closed loop... (keep the short/long term trim value)
				pass 
			else: # if we're outside of closed loop just set the % error to 1 (no correction)
				sample.Value = 1
		else: # if we're outside of engine temperature, rev limit, min & max normalized map just set the $ error to 1 (no correction)
			sample.Value = 1.0
		
	plotAccepted = True
	
	error_perc = (((trim - 1.0) * error_multiplier) + 1) * twistgrip/twistgrip
			
	if plotAccepted:
		return error_perc
	else:
		return None
	
#ensure that we've got logfiles loaded in Data Center...
if context.EnsureFiles():
	try:
		#create a table the same dimensions as VE and fill it with error data with weighted hitcount > hit_value
		error = tunelab.generate_sample_table(context.GetTable(correction_table), calc_error_channel, None, hit_value)
		#allow the user to edit/review the corrected VE values
		error = edit(error)
		if error != None:
			#multiply the %error into VE to generate a correction and place the result back into the document
			context.PutTable(error * context.GetTable(correction_table))
	finally:
		#always clean up any files that we might have opened at the start
		context.FreeFiles()
		
# Routine to correct the ICF Tables

cylinder_front = "front"
cylinder_rear = "rear"

#the table to be corrected. Change this to target another table
correction_table1 = "Injector Compensation Factor Front"
correction_table2 = "Injector Compensation Factor Rear"

#Callback passed to generate_sample_table that creates the corrected IPW channel 
def calc_error_channel(fileHandle):
	requested = channels.GetChannelByName("Requested AFR", fileHandle)
	shortTermFront = channels.GetChannelByName("Short term fuel trim front", fileHandle)
	longTermFront = channels.GetChannelByName("Long term fuel trim front", fileHandle)
	shortTermRear = channels.GetChannelByName("Short term fuel trim rear", fileHandle)
	longTermRear = channels.GetChannelByName("Long term fuel trim rear", fileHandle)
	engine_temp = channels.GetChannelByName("Engine Temperature", fileHandle)
	rpm_value = channels.GetChannelByName("Engine Speed", fileHandle)
	normalized_map = channels.GetChannelByName("Normalized MAP for VE", fileHandle)
	loadrequest = channels.GetChannelByName("Load Request", fileHandle)
	twistgrip = channels.GetChannelByName("Twist Grip Position", fileHandle)
	
	#This filter removes all samples that have negative slope (used as decel filter)
	dc = tlfiltersCBCM.SlopeFilter(decel_slope)
	dc.do_filter(None, None, twistgrip.GetAllSamples())

	#This filter removes samples that equal the stft_open
	stftfilter = tlfiltersCBCM.BasicDeleteZFilter(stft_open)
	stftfilter.do_filter(None, None, shortTermFront.GetAllSamples())
	stftfilter.do_filter(None, None, shortTermFront.GetAllSamples())
	
	#--------------------------------------------------------------------------
	trimFront = (((shortTermFront) + (longTermFront)) / 100.0) + 1.0
	trimRear =  (((shortTermRear) + (longTermRear)) / 100.0) + 1.0
	trAV = ((trimFront) + (trimRear)) / 2.0  
	# final trim shall be relative to average instead of 14.7 ... because we do averaged(!) VE corrections later based on requested
	if cylinder == "front":
		trim = trimFront / trAV * shortTermFront/shortTermFront
	elif cylinder == "rear":
		trim = trimRear / trAV * shortTermRear/shortTermRear
	#--------------------------------------------------------------------------


	for sample in trim.GetAllSamples():
		#don't tune the area at all if engine temp isn't up!
		if engine_temp.GetValueAtTime(sample.TimeMillis) >= engine_temp_thresh and rpm_value.GetValueAtTime(sample.TimeMillis) <= rev_max and rpm_value.GetValueAtTime(sample.TimeMillis) > rev_min and normalized_map.GetValueAtTime(sample.TimeMillis) > min_ve_map and normalized_map.GetValueAtTime(sample.TimeMillis) < max_ve_map and loadrequest.GetValueAtTime(sample.TimeMillis) > min_load and loadrequest.GetValueAtTime(sample.TimeMillis) < max_load:
			requested_value = requested.GetValueAtTime(sample.TimeMillis)
			if requested_value == closed_loop_val:
				#we're in closed loop... (keep the short/long term trim value)
				pass
			else: # if we're outside of closed loop just set the % error to 1 (no correction)
				sample.Value = 1.0
		else:
			sample.Value = 1.0

	plotAccepted = True


	error_perc = (((trim - 1.0) * error_multiplier) + 1) * twistgrip/twistgrip


	if plotAccepted:
		return error_perc
	else:
		return None

#ensure that we've got logfiles loaded in Data Center...
if context.EnsureFiles():
	try:
		cylinder = cylinder_front
		#### TABLE 1 ######
		#create a table the same dimensions as ICF Table and fill it with error data with weighted hitcount > hit_value
		error = tunelab.generate_sample_table(context.GetTable(correction_table1), calc_error_channel, None, hit_value)
		#allow the user to edit/review the corrected ICF values
		error = edit(error)
		if error != None:
			#multiply the %error into ICF Table to generate a correction and place the result back into the document
			context.PutTable(error * context.GetTable(correction_table1))

			cylinder = cylinder_rear #switch to rear cylinder before rerunning correction
			###### TABLE 2 #######
			#create a table the same dimensions as ICF Table and fill it with error data with weighted hitcount > hit_value
			error = tunelab.generate_sample_table(context.GetTable(correction_table2), calc_error_channel, None, hit_value)
			#allow the user to edit/review the corrected ICF values
			error = edit(error)
			if error != None:
				#multiply the %error into ICF Table to generate a correction and place the result back into the document
				context.PutTable(error * context.GetTable(correction_table2))

				
	finally:
		#always clean up any files that we might have opened at the start
		context.FreeFiles()
