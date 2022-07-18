#Short Term Plug Long Term Fuel Trim correction
import tlfilters
#Open formula editor to change filtering parameters

show_plot = True

#Set smoothing higher for more smoothing, lower for less smoothing
smoothing = 500.0

#any samples below min_afr will be deleted
min_afr = 10

#any samples above max_afr will be deleted
max_afr = 19

#the table to be corrected. Change this to target another table
correction_table = "Volumetric Efficiency"

cached_afr = {}


#Callback passed to generate_sample_table that creates the % error channel from AFR1
def calc_error_channel_ol(fileHandle):
	afr1 = context.AFR1(fileHandle)

	#do a lowpass filter on the AFR data to remove noise. The higher the number, the more smoothing will be applied.
	filter1 = tlfilters.LowpassFilter(smoothing)
	filter1.do_filter(None, None, afr1.GetAllSamples())
	
	#This filter removes samples below 10 and above 19. This filter also removes some samples adjacent to any values that go above the threshold.
	#if too much data is being removed, you can adjust the min and max values
	filter2 = tlfilters.TimeMinMaxZFilter(min_afr,max_afr)
	filter2.do_filter(None, None, afr1.GetAllSamples())
	
	plotCancelled = False
	
	if show_plot:
		#show plot of AFR
		plotCancelled = not context.Plot(afr1.GetAllSamples(), text="Review and trim %s from %s" % (afr1.GetName(), afr1.GetSourceFileName()), yAxisText=afr1.GetName())
		
		

	if not plotCancelled:
		requested = channels.GetChannelByName("Requested AFR", fileHandle)

		filter3 = tlfilters.BasicMinMaxZFilter(10, 14.6999)
		filter3.do_filter(None, None, requested.GetAllSamples())

		#uncomment this line if you wish to view requested AFR on a plot
		#plotCancelled = not context.Plot(requested.GetAllSamples(), text="Review filtered AFR")
		
		#divide the averaged channel by the requested afr channel - this produces a % error channel
		return afr1/requested
	else:
		return None

def calc_error_channel_cl(fileHandle):
	trim = channels.GetChannelByName("Short term fuel trim", fileHandle)
	longTerm = channels.GetChannelByName("Long term fuel trim", fileHandle)
	trim = trim+longTerm
	requested = channels.GetChannelByName("Requested AFR", fileHandle)
	
	NaN = float("NaN")

	clFilter = tlfilters.BasicMinMaxZFilter(14.7, 14.7)
	clFilter.do_filter(None, None, requested.GetAllSamples())
	
	#Filter the requested channel and ensure only 14.7 is set.
	#THEN zero it out (all filtered samples are NaN). Adding to trim will essentially cause an AND operation and remove all samples where requested wasn't 14.7
	trim = trim + (requested * 0)
	for sample in trim.GetAllSamples():
		if sample.Value == 0:
			sample.Value = NaN


	context.Plot(trim.GetAllSamples(), text="Review Short Term Trim Data", yAxisText=trim.GetName())
	return (trim+100)/100.0


#ensure that we've got logfiles loaded in Data Center...
if context.EnsureFiles():
	try:
		
		trimTable = tunelab.generate_sample_table(context.GetTable(correction_table), calc_error_channel_cl)
		if trimTable is not None:
			trimTable = edit(trimTable)
			if trimTable is not None:
				context.PutTable(context.GetTable(correction_table) * (trimTable))
				
		error = tunelab.generate_sample_table(context.GetTable(correction_table), calc_error_channel_ol)
		
		if error is not None:
			#allow the user to edit/review the % error table
			error = edit(error)
			if error is not None:
				#multiply the %error into the two tables to generate a correction and place the result back into the document
				context.PutTable(context.GetTable(correction_table) * error)


	finally:
		#always clean up any files that we might have opened at the start
		context.FreeFiles()
