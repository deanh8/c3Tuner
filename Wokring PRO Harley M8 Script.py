#All Trims PRO
#Apply long and short term trims to tables when in closed loop (determined by comparing requested AFR to the lambda range table)
#When not in closed loop, apply WBAFR data (open loop area) if WB O2 sensor is connected. 
#Note that if you are using a WBCX instead of DWRT AFR, the smoothing variable should be set to 2 instead of 500
import tlfilters

#set this to true if you're using a PVT file rather than a DJT
pvt_correction = True


show_plot = True

#Get the closed loop min / max from the calibration itself
lambdaRangeTable = context.GetTable("Lambda Range")

if pvt_correction:
	#filter out samples when requested afr is less than this value
	closed_loop_min = lambdaRangeTable.GetZValue(0, 1)

	#filter out samples when requested afr is greater than this value
	closed_loop_max = lambdaRangeTable.GetZValue(0, 0);
else:
	#filter out samples when requested afr is less than this value
	closed_loop_min = lambdaRangeTable.GetZValue(1, 0)

	#filter out samples when requested afr is greater than this value
	closed_loop_max = lambdaRangeTable.GetZValue(0, 0);

max_wb_afr = 19.0
min_wb_afr = 10.0 

#This number controls how aggressive corrections are.
#default is 1.05 = 5% (meaning corrections will be increased in aggressiveness by 5%)
error_multiplier = 1.00


#set this to decide which temperature tuning will begin at (engine temp must be greater than this value)
engine_temp_thresh = channels.Convert(175, "F") #ensure temperature units are set to F

#rc filter constant
#this is used to set the smoothing level for WB AFR data.
#Higher numbers mean more smoothing. Default is 100.
#Set this to 2 if using a WBCX instead of a DWRT WB. 
smoothing = 100

cylinder_front = "Front"
cylinder_rear = "Rear"
cylinder = cylinder_front
#the table to be corrected. Change this to target another table
correction_table1 = "Volumetric Efficiency TPS-Based Front Cylinder"
correction_table2 = "Volumetric Efficiency TPS-Based Rear Cylinder"

#Callback passed to generate_sample_table that creates the corrected VE channel 
def calc_error_channel(fileHandle):
	
	if pvt_correction:
		requested = channels.GetChannelByName("Desired Lambda", fileHandle)
		if requested is not None:
			requested = requested * 14.7
		else:
			requested = channels.GetChannelByName("Desired Air/Fuel (Ratio)", fileHandle)


	shortTerm = channels.GetChannelByName("%s Adaptive Fuel Factor" % cylinder, fileHandle)
	longTerm = channels.GetChannelByName("%s Closed Loop Integrator" % cylinder, fileHandle)
	ve_actual = channels.GetChannelByName("VE %s" % cylinder, fileHandle)
	if cylinder == "Front":
		afr = context.AFR1(fileHandle)
	elif cylinder == "Rear":
		afr = context.AFR2(fileHandle)
	else:
		raise Exception("Invalid cylinder selected!")

	engine_temp = channels.GetChannelByName("Engine Temperature", fileHandle)
	
	#calculate the combined factor for closed loop fuel adjustment
	trim = (((shortTerm - 100.0) + (longTerm - 100.0)) / 100.0) + 1.0

	
	if afr is not None:
		#rc = tlfilters.LowpassFilter(rc=smoothing)
		#rc.do_filter(None, None, afr.GetAllSamples())
		
		minMaxFilter = tlfilters.BasicMinMaxZFilter(min=min_wb_afr, max=max_wb_afr)
		minMaxFilter.do_filter(None, None, afr.GetAllSamples())

		afr.Smooth(smoothing)
	
	for sample in trim.GetAllSamples():
		#don't tune the area at all if engine temp isn't up!
		if engine_temp.GetValueAtTime(sample.TimeMillis) >= engine_temp_thresh:
			requested_value = requested.GetValueAtTime(sample.TimeMillis)
			if requested_value >= closed_loop_min and requested_value <= closed_loop_max:
				#we're in closed loop... (keep the short/long term trim value)
				#print "using closed loop value %f" % sample.Value
				pass 
			elif afr is not None:
				sample.Value = afr.GetValueAtTime(sample.TimeMillis) / requested_value
			else: # if we're outside of closed loop just set the % error to 1 (no correction)
				sample.Value = 1
		else:
			sample.Value = 1.0
				
	plotAccepted = True
	
	if show_plot:
		#show plot of AFR
		plotAccepted = context.Plot(trim.GetAllSamples(),text="Review and trim %s from %s" % ("Corrected VE %s" % cylinder, trim.GetSourceFileName()), yAxisText="Corrected VE %s" % cylinder)
	
	if plotAccepted:
		return ((trim - 1.0) * error_multiplier) + 1
	else:
		return None
	
#ensure that we've got logfiles loaded in Data Center...
if context.EnsureFiles():
	try:
		#### TABLE 1 ######
		#create a table the same dimensions as VE and fill it with corrected VE data
		error = tunelab.generate_sample_table(context.GetTable(correction_table1), calc_error_channel)
		
		if error != None:
			#allow the user to edit/review the corrected VE values
			error = edit(error * 100.0 - 100.0)
			if error != None:
				error = (error+100.0)/100.0
				#put the corrected cells into the VE table
				context.PutTable(error * context.GetTable(correction_table1))
				cylinder = cylinder_rear #switch to rear cylinder before rerunning correction
				###### TABLE 2 #######
				#create a table the same dimensions as the VE table and fill it with corrected VE channel data
				error = tunelab.generate_sample_table(context.GetTable(correction_table2), calc_error_channel)
				
				if error != None:
					#allow the user to edit/review the corrected VE values
					error = edit(error * 100.0 - 100.0)
					if error != None:
						error = (error+100.0)/100.0
						#Insert the corrected VE channel data into the VE table
						context.PutTable(error * context.GetTable(correction_table2))
						
				
	finally:
		#always clean up any files that we might have opened at the start
		context.FreeFiles()



