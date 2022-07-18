#V1.0 Yamaha Per-Cylinder script.
#Note: Requires a sensor PER CYLINDER to work correctly.
#You will need to use two Dual Autotune modules.
#Autotune module 0 should be connected to cylinders 1 and 2, and autotune module 1 should be connected to cylinders 3 and 4 (if present on the bike).
#If this script is being used for an MT09, you will need to adjust the "cylinderCount" variable to 3 instead of 4!
import math
import tlfilters

defaultTargetAfr = 13

maxAfr = 19
minAfr = 10


doSingleChannelCorrection = True


#Use 500 for Dyno AFR, use 2 for onboard AFR (WB2, WB3, etc)
#Higher values = more smoothing
smoothing = 500


#Should be alpha N table names, speed density table names. Do not adjust unless you know what you're doing.
#Must include a trailing space!
anTableName = 'Alpha N Cylinder '
sdTableName = 'Speed Density Cylinder '


#Adjust for MT09 or R1
cylinderCount = 4

#Do not adjust, global during script operation
cylinderIndex = 0



#load target table from document storage (so we can keep our AFR target settings around between iterations of this script)
targetTable = context.GetTable("AFR Target")

def generate_biased_sample_table(protoTableA, protoTableB, zChannelArg, get_bias):
	
	#generate our output table. This is where samples will be placed.
	tableA = protoTableA.Clone()
	tableB = protoTableB.Clone()

	#these will be our z values (data). 
	zValuesA = tunelab.matrix(protoTableA.Width, protoTableA.Height)
	zValuesB = tunelab.matrix(protoTableB.Width, protoTableB.Height)

	#We need to keep track of the hit count for each cell so we can correctly average the values that have accumulated
	hitCountA = tunelab.matrix(protoTableA.Width, protoTableA.Height)
	hitCountB = tunelab.matrix(protoTableB.Width, protoTableB.Height)
	
	#We need to go through each loaded file index
	for fileHandle in channels.GetFileHandles():
		
		#Get our channels for this file handle
		xChannelA = protoTableA.GetXChannel(fileHandle)
		yChannelA = protoTableA.GetYChannel(fileHandle)

		xChannelB = protoTableB.GetXChannel(fileHandle)
		yChannelB = protoTableB.GetYChannel(fileHandle)
		
		zChannel = zChannelArg(fileHandle)
		
		

		#Ensure we have valid channels for each axis. We can't fill the table if an axis is missing a channel to associate to
		if xChannelA != None and yChannelA != None and zChannel != None:
			
			xChannelDataA = xChannelA.GetAllSamples()
			yChannelDataA = yChannelA.GetAllSamples()
			
			xChannelDataB = xChannelB.GetAllSamples()
			yChannelDataB = yChannelB.GetAllSamples()

			zChannelData = zChannel.GetAllSamples()
				
				
			for zSample in zChannelData:
				
				if zSample is not None and not math.isnan(zSample.Value):
					time = zSample.TimeMillis
					
					
					if time >= 0:
						xA = tunelab.get_value_at_time(xChannelDataA, time)
						yA = tunelab.get_value_at_time(yChannelDataA, time)
						
						xB = tunelab.get_value_at_time(xChannelDataB, time)
						yB = tunelab.get_value_at_time(yChannelDataB, time)
						
						bias = get_bias(time, fileHandle)

						#bias toward the A table. 
						# if bias = 1, table A gets 100% of the correction.
						# if bias = 0, table B gets 100% of the correction
						

						#SIDE A
						if not math.isnan(xA) and not math.isnan(yA) and not math.isinf(xA) and not math.isinf(yA):
							xIdx,percentX = tunelab.axis_place_value(protoTableA.GetXValues(), xA)
							yIdx,percentY = tunelab.axis_place_value(protoTableA.GetYValues(), yA)
							
							#print "X: %f Y: %f Z: %f" % (x, y, zSample.Value)
								
							if xIdx != -1 and yIdx != -1:
								if percentX >= 0.5:
									xIdx += 1
									percentX -= 1.0
								
								if percentY >= 0.5:
									yIdx+=1
									percentY -= 1.0
								
							#Weight our sample based on how close to the center of the cell it is... 
							weight = math.fabs(percentX) + math.fabs(percentY)
							
							#invert value because percentX/Y are the percentage AWAY from the center
							weight = 1.0 - weight
							
							
							hitCountA[xIdx][yIdx] += weight * bias
							zValuesA[xIdx][yIdx] += zSample.Value * weight * bias
						
						#SIDE B
						if not math.isnan(xB) and not math.isnan(yB) and not math.isinf(xB) and not math.isinf(yB):
							#invert bias for side B
							bias = 1.0 - bias
							xIdx,percentX = tunelab.axis_place_value(protoTableB.GetXValues(), xB)
							yIdx,percentY = tunelab.axis_place_value(protoTableB.GetYValues(), yB)
							
							#print "X: %f Y: %f Z: %f" % (x, y, zSample.Value)
								
							if xIdx != -1 and yIdx != -1:
								if percentX >= 0.5:
									xIdx += 1
									percentX -= 1.0
								
								if percentY >= 0.5:
									yIdx+=1
									percentY -= 1.0
								
							#Weight our sample based on how close to the center of the cell it is... 
							weight = math.fabs(percentX) + math.fabs(percentY)
							
							#invert value because percentX/Y are the percentage AWAY from the center
							weight = 1.0 - weight
							
							
							hitCountB[xIdx][yIdx] += weight * bias
							zValuesB[xIdx][yIdx] += zSample.Value * weight * bias
		else:
			return None

	#Now average our values out based on hit counts for each cell, then place the values into the result table.
	#Any cells that were not changed should be set to NaN so that we don't change values for cells with no data. (The PutTable call won't touch NaN cells)

	#SIDE A
	for xIdx in range(protoTableA.Width):
		for yIdx in range(protoTableA.Height):
			
			if hitCountA[xIdx][yIdx] > 0:
				zValue = zValuesA[xIdx][yIdx] / hitCountA[xIdx][yIdx]
				
				#Todo: check for infinity
	
				tableA.PutZValue(xIdx, yIdx, zValue)
	
			else:
				tableA.PutZValue(xIdx,yIdx, math.nan)
	#SIDE B
	for xIdx in range(protoTableB.Width):
		for yIdx in range(protoTableB.Height):
			
			if hitCountB[xIdx][yIdx] > 0:
				zValue = zValuesB[xIdx][yIdx] / hitCountB[xIdx][yIdx]
				
				#Todo: check for infinity
	
				tableB.PutZValue(xIdx, yIdx, zValue)
	
			else:
				tableB.PutZValue(xIdx,yIdx, math.nan)
		
	return (tableA,tableB)


#Internal variables
biasChannel = None
currFileHandle = -1

def getBiasValue(time, fileHandle):
	global currFileHandle
	global biasChannel

	if currFileHandle != fileHandle:
		biasChannel = channels.GetChannelByName("Bias Alpha N", fileHandle)
		currFileHandle = fileHandle
	
	
	value = biasChannel.GetValueAtTime(time)
	if value < 0.0:
		value = 0.0
	if value > 100.0:
		value = 100.0

	return value/100.0

def calcCorrection_wideband(fileHandle):
		
	xChan = targetTable.GetXChannel(fileHandle)
	yChan = targetTable.GetYChannel(fileHandle)

	if xChan is not None and yChan is not None:
		
		deviceIndex = int(cylinderIndex / 2)
		channelNumber = ((cylinderIndex) % 2) + 1

		if doSingleChannelCorrection:
			afr = context.AFR1(fileHandle)
		else:
			afr = channels.GetChannelByName("Dual Autotune.General.Air/Fuel Ratio %d[%d]" % (channelNumber, deviceIndex), fileHandle)

		if afr is not None: #Ensure AFR is valid...
			
			#remove all samples that aren't min/max
			afrFilter = tlfilters.BasicMinMaxZFilter(minAfr, maxAfr)
			afrFilter.do_filter(None, None, afr.GetAllSamples())

			rcFilter = tlfilters.LowpassFilter(smoothing)
			rcFilter.do_filter(None, None, afr.GetAllSamples())

			
			if context.Plot(afr.GetAllSamples(), text="Review Cylinder %d %s from %s" % (cylinderIndex+1, afr.GetName(), afr.GetSourceFileName()), yAxisText=afr.GetName()): # Let the user trim up the AFR channel if they want to
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
	global cylinderIndex
	try:


		if doSingleChannelCorrection:
			sdTable = context.GetTable("%s%d" % (sdTableName, (1)))
			anTable = context.GetTable("%s%d" % (anTableName, (1)))
			
			alphaError,sdError = generate_biased_sample_table(anTable, sdTable, calcCorrection_wideband, getBiasValue)
			alphaError = edit(alphaError)
			if alphaError is not None:
				sdError = edit(sdError)
				if sdError is not None:
					for i in range(0,cylinderCount):
						sdTable = context.GetTable("%s%d" % (sdTableName, (i+1)))
						anTable = context.GetTable("%s%d" % (anTableName, (i+1)))
						context.PutTable(anTable * alphaError)
						context.PutTable(sdTable * sdError)

		else:
			for i in range(0,cylinderCount):
				cylinderIndex = i
				sdTable = context.GetTable("%s%d" % (sdTableName, (i+1)))
				anTable = context.GetTable("%s%d" % (anTableName, (i+1)))

				if targetTable is not None:
					#targetTable = edit(targetTable)
					if targetTable is not None:
						
						alphaError,sdError = generate_biased_sample_table(anTable, sdTable, calcCorrection_wideband, getBiasValue)
						if alphaError is not None and sdError is not None:

							alphaError = edit(alphaError)
							if alphaError is not None:
								sdError = edit(sdError)
								if sdError is not None:
									#Apply table changes!
									context.PutTable(anTable * alphaError)
									context.PutTable(sdTable * sdError)
								else:
									break
							else:
								break
						else:
							break
					else:
						break
				else:
					context.Alert("No target AFR table available. Please ensure you have the latest definition.")
					
	finally:
		context.FreeFiles()
