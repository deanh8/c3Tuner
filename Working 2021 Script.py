#Per-Cylinder VE correction for Harley.
import tlfilters

#set this to true if you're using a PVT file rather than a DJT
pvt_correction = True

show_plot = True

#Set smoothing higher for more smoothing, lower for less smoothing
smoothing = 100

#any samples below min_afr will be deleted
min_afr = 10

#any samples above max_afr will be deleted
max_afr = 19

#the table to be corrected. Change this to target another table
correction_table1 = "VE (TPS based/Front Cyl)"
correction_table2 = "VE (TPS based/Rear Cyl)"

currentCorrectionTable = None

#Callback passed to generate_sample_table that creates the % error channel from AFR1
def calc_error_channel(fileHandle):

	afr1 = None
	afr2 = None
	side = None
	#depending on whether we're doing the front or rear cylinder correction, grab the appropriate AFR channel.
	if currentCorrectionTable == correction_table1:
		afr1 = context.AFR1(fileHandle)
		side = "AFR 1"
	elif currentCorrectionTable == correction_table2:
		afr2 = context.AFR2(fileHandle)
		side = "AFR 2"

	
	#This filter removes samples below 10 and above 19. This filter also removes some samples adjacent to any values that go above the threshold.
	#if too much data is being removed, you can adjust the min and max values
	filter2 = tlfilters.TimeMinMaxZFilter(min_afr,max_afr)
	
	
	afr1Valid = False
	afr2Valid = False
	if afr1 is not None:
		filter2.do_filter(None, None, afr1.GetAllSamples())
		afr1.Smooth(smoothing)
		for sample in afr1.GetAllSamples():
			if sample.IsValid:
				afr1Valid = True
				break

	if afr2 is not None:
		filter2.do_filter(None, None, afr2.GetAllSamples())
		afr2.Smooth(smoothing)
		for sample in afr2.GetAllSamples():
			if sample.IsValid:
				afr2Valid = True
				break
	
	if afr1Valid and afr2Valid:
	# the code to average channels is still here, but we actually just perform individual cylinder corrections!
		average_afr = (afr1 + afr2) / 2.0
	elif afr1Valid:
		average_afr = afr1
	elif afr2Valid:
		average_afr = afr2
	else:
		context.Alert("Missing or invalid %s data in log %s" % (side, channels.GetFileName(fileHandle)))
		return None


	plotAccepted = True
	
	if show_plot:
		#show plot of AFR
		plotAccepted = context.Plot(average_afr.GetAllSamples(),text="Review and trim %s from %s" % (average_afr.GetName(), average_afr.GetSourceFileName()), yAxisText=average_afr.GetName())
	
	if plotAccepted:

		if pvt_correction:
			requested = channels.GetChannelByName("Desired Lambda", fileHandle)
			if requested is not None:
				requested = requested * 14.7
		else:
			requested = channels.GetChannelByName("Desired Air/Fuel (Ratio)", fileHandle)
		

		requestedValid = False
		if requested is not None:
			for sample in requested.GetAllSamples():
				if sample.IsValid:
					requestedValid = True
					break
		
		if requestedValid:
			#uncomment this line if you wish to view requested AFR on a plot
			#context.Plot(requested.GetAllSamples(), text="Review filtered AFR")
			
			#divide the averaged channel by the requested afr channel - this produces a % error channel
			return average_afr/requested
		else:
			context.Alert("Target AFR channel not valid in file %s" % channels.GetFileName(fileHandle))
	else:
		return None

def DoCorrection():
	retval = False
	table = context.GetTable(currentCorrectionTable)

	if table is not None:
		
		#create a table the same dimensions as VE and fill it with error data
		error = tunelab.generate_sample_table(table, calc_error_channel)
		
		if error != None:
			#allow the user to edit/review the % error table
			error = edit(error * 100.0 - 100)
			if error != None:
				#multiply the %error into the two tables to generate a correction and place the result back into the document
				context.PutTable(table * ((error + 100.0) / 100.0))
				retval = True
	else:
		context.Alert("Unable to find correction table")
	
	return retval
	
#ensure that we've got logfiles loaded in Data Center...
if context.EnsureFiles():
	try:
		currentCorrectionTable = correction_table1
		if DoCorrection():
			currentCorrectionTable = correction_table2
			DoCorrection()
	finally:
		#always clean up any files that we might have opened at the start
		context.FreeFiles()


