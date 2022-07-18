#GROM Wideband/Narrowband Combined Correction
#This correction requires wideband input - a correction % will be calculated using narrowbands and a virtual target AFR table.
#The target AFR table is edited each time the script is run, and its value is persisted between iterations, but only
#inside the current document. 
#If trims are enabled (via useTrims), the script will also use vehicle trims to calculate a correction. Trims take precedence
#over wideband data - if a cell has both narrowband and wideband corrections, the wideband correction will be replaced
#with the narrowband correction. 
import math
import tlfilters

defaultTargetAfr = 13

maxAfr = 19
minAfr = 10

#if True, correct using narrowband trims in addition to wideband data.
useTrims = True

#Use 500 for Dyno AFR, use 2 for onboard AFR (WB2, WB3, etc)
#Higher values = more smoothing
smoothing = 500

correctionTable = "Injector Pulsewidth, Normal"

#load target table from document storage (so we can keep our AFR target settings around between iterations of this script)
targetTable = context.DocLoad("targetAfrTable")


def calcCorrection_narrowband(fileHandle):
	
	shortTerm = channels.GetChannelByName("Short Term Fuel Trim", fileHandle)
	longTerm = channels.GetChannelByName("Long Term Fuel Trim", fileHandle)

	if shortTerm is not None and longTerm is not None:
		trims = (shortTerm + longTerm)

		#simply remove trims altogether where samples are 0, we don't want 0 cells in our correction.
		for sample in trims.GetAllSamples():
			if sample.Value == 0:
				sample.Value = float("nan")

		return trims
	else:
		context.Alert("Missing narrowband trim channels in file %s" % channels.GetFileName(fileHandle))

	return None


def calcCorrection_wideband(fileHandle):
		
	xChan = targetTable.GetXChannel(fileHandle)
	yChan = targetTable.GetYChannel(fileHandle)

	if xChan is not None and yChan is not None:
		afr = context.AFR1(fileHandle)
		
		
		if afr is not None: #Ensure AFR is valid...
			
			#remove all samples that aren't min/max
			afrFilter = tlfilters.BasicMinMaxZFilter(minAfr, maxAfr)
			afrFilter.do_filter(None, None, afr.GetAllSamples())

			rcFilter = tlfilters.LowpassFilter(smoothing)
			rcFilter.do_filter(None, None, afr.GetAllSamples())

			
			if context.Plot(afr.GetAllSamples(), text="Review and trim %s from %s" % (afr.GetName(), afr.GetSourceFileName()), yAxisText=afr.GetName()): # Let the user trim up the AFR channel if they want to
				for sample in afr.GetAllSamples(): #Calculate error for each AFR sample!
					
					xVal = xChan.GetValueAtTime(sample.TimeMillis)
					yVal = yChan.GetValueAtTime(sample.TimeMillis)
					
					if not math.isnan(xVal) and not math.isnan(yVal):
						targetValue = targetTable.Lookup(xVal, yVal)
						sample.Value = sample.Value / targetValue
					else:
						sample.Value = float("nan")


				
				return afr
		else:
			context.Alert("No valid Air/Fuel channel available in %s" % channels.GetFileName(fileHandle))
	else:
		context.Alert("Missing axis channel(s) in %s" % channels.GetFileName(fileHandle))

	return None
	


if context.EnsureFiles():
	try:
		
		#if there's no target table loaded, just create a default one. 
		if targetTable is None:
			targetTable = context.GetTable("Injector Pulsewidth, Normal")
			targetTable.Clear(defaultTargetAfr) #start with initial target AFR of 13.0 for whole table.
			targetTable.Name = "Target AFR"

		
		if targetTable is not None:

			targetTable = edit(targetTable)
			if targetTable is not None:
				context.DocStore("targetAfrTable", targetTable)
				table = context.GetTable(correctionTable)

				errorTable = tunelab.generate_sample_table(table, calcCorrection_wideband)

				if errorTable is not None:
					errorTable = errorTable * 100.0 - 100# show the error table as a percentage for nicer viewing.
					errorTable.Name = "Percent Correction (%)"

					if useTrims:
						#we need the trims table here...
						trimTable = tunelab.generate_sample_table(table, calcCorrection_narrowband)
						if trimTable is not None:
							trimTable.Name = "Narrowband Trim Percentage (%)"
							#trimTable = edit(trimTable)
							if trimTable is not None:
								#OR the trim and error tables together, preferring the values from the trim side. 
								#Any wideband corrections that also land on cells with narrowband corrections will be replaced
								#with narrowband corrections (they take precedence)
								errorTable = trimTable | errorTable
								errorTable.Name = table.Name + " - Wideband corrections and Trims %"

					errorTable = edit(errorTable)
					if errorTable is not None:
						errorTable = (errorTable + 100 ) / 100.0 # convert back to a factor
						context.PutTable(table * errorTable)

	finally:
		context.FreeFiles()
