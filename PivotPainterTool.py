# 
# Copyright 2018 GEORGE VOGIATZIS 
#
# Licensed under the EUPL, Version 1.1 or – as soon they will be approved by the European Commission - subsequent versions of the EUPL (the "Licence");
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at:
# 
# https://joinup.ec.europa.eu/software/page/eupl
#
# Unless required by applicable law or agreed to in writing, software distributed under the Licence is distributed on an "AS IS" basis,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the Licence for the specific language governing permissions and limitations under the Licence.
#

bl_info = {
    "name": "Pivot Painter",
    "author": "George Vogiatzis",
    "version": (0, 7),
    "blender": (2, 79, 0),
    "location": "View3D > Tool Shelf > Unreal Tools",
    "description": "Tools to create 3d model for Unreal Engine 4, that make use of the Pivot Painter Tool's material functions",
    "warning": "Untested",
    "wiki_url": "",
    "category": "Unreal Tools",
    }

import time
import bpy
import math
import ctypes # not need
import mathutils
import numpy as np
import random
from ctypes import *
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import BoolProperty, PointerProperty,IntProperty
from math import floor, ceil, sqrt


def findTextureDimensions ():																				# Try to find efficient texture dimensions for the total number of object
	
	ObjectToProcessCount = len(bpy.context.selected_objects)
	DecrementerTotal = 1600 # small enough to avoid uv precision issues without using high precision values # If UV use half float, shoudn't be 1024? And what about the number of objects indexing? 256 should be the max in this case(although higher may be more efficient, but does it matter in that point?).
	
	HalfEvenNumber = ((ObjectToProcessCount/2) % 2)
	HalfNumber = ceil(ObjectToProcessCount/2)
	modResult = 1
	RowCounter = 1
	
	if HalfNumber < DecrementerTotal :	# highest possible x dimension
		newDecrementerTotal = HalfNumber
	else:
		newDecrementerTotal = DecrementerTotal
	
	if HalfEvenNumber==0:
		decrementAmount = 2
	else:
		decrementAmount = 1
	
	complete = False
	while complete == False:			# tries to find y dimension by checking the mod=0 
		modResult = ObjectToProcessCount % newDecrementerTotal
		if modResult==0 or newDecrementerTotal < 1:
			complete = True
		if complete == False:
			newDecrementerTotal -= decrementAmount
		if newDecrementerTotal < 1:
			newDecrementerTotal=1
	
	if newDecrementerTotal == 1 or ((ObjectToProcessCount/newDecrementerTotal)>DecrementerTotal):
		Y = floor(sqrt(ObjectToProcessCount))
		X = ceil(ObjectToProcessCount/floor(Y))
		size=[X,Y]
	else:
		size=[newDecrementerTotal,(ObjectToProcessCount//newDecrementerTotal)]
	return size


def createUVMap(size,props): 																				# Create uvmap with point coordinates per opject
	
	counter = 0
	bpy.context.scene.objects.active = bpy.context.selected_objects[0] # join function needs an active object 
	x=[] # WHY? simple float in the loop would be fine. will I need it elsewere?
	y=[]
	
	for obj in bpy.context.selected_objects:
		if props.automaticindexselect == True:
			obj.data.uv_textures.new(name = "PivotPainterMap") # it will not create if already 8 uvmap(max)
			layernumber = len(obj.data.uv_textures)-1 # will use the last layer
		else:
			layernumber = props.uvindex
			while len(obj.data.uv_layers) <= layernumber:			# Create enought layers to reach target
				obj.data.uv_textures.new(name = "PivotPainterMap") 
			
		
		x.append(counter%size[0]/size[0]+1/size[0]/2)
		y.append(1-(floor(counter/size[0])/size[1]+1/size[1]/2)) # Already inverted for combatibility with UE4 Pivot Paint Tool shaders. # in future version I can invert wiht a bool select for consistency with maxscript(but doesnot make sense to do now, as it is only for visual). Also will need to invert at the textures functions that will be a bit more complicated.
		
		for poly in obj.data.polygons:
			for vertId, loopId in zip(poly.vertices, poly.loop_indices):
				obj.data.uv_layers[layernumber].data[loopId].uv = (x[-1],y[-1])
		
		counter = counter + 1


def convert(s):																								# hex to float.
	i = int(s, 16)						# convert from hex to a Python int
	cp = pointer(c_int(i))				# make this into a c integer
	fp = cast(cp, POINTER(c_float))		# cast the int pointer to a float pointer
	return fp.contents.value			# https://stackoverflow.com/questions/1592158/convert-hex-to-float Is this method coorect? maybe the result is similar but not the same.


def packTextureBits(index): 																				# Store Int to flot 
	index = int(index)									# Not sure why is this necessary , and doesn't simpy put the integer bits into the float directlry. but it gets reverse in shader custom code. I include it for consistency, and ease of use.
	index = index +1024									# Need to check how the change from 32 float to 16(the exponent is the suspect) when saving affects the bits, if it does, probably the reason for this fucntion. Otherwise I don't understand why cannot put int as float(and use 2^8 precision).
	sigh=index&0x8000
	sigh=sigh<<16
	# print(sigh)
	exptest=index&0x7fff
	if exptest==0:
		exp=0
	else:
		exp=index>>10
		exp=exp&0x1f
		exp=exp-15
		exp=exp+127
		exp=exp<<23
	mant=index&0x3ff
	mant=mant<<13
	index=sigh|exp|mant
	
	testb=hex(index)
	testb=convert(testb)
	return testb


def findrgbfunction(texturergb, hdr):																		# Select the rgb fuction
	if texturergb == 'PivotPoint' :	
		rgbfunction = pivotarray
		hdr = True						# For texture type
	elif texturergb == 'Xaxis' :
		rgbfunction = xaxisArray
	elif texturergb == 'Yaxis' :
		rgbfunction = yaxisArray
	elif texturergb == 'Zaxis' :
		rgbfunction = zaxisArray		
	elif texturergb == 'OriginPosition' :
		rgbfunction = originArray
		hdr = True
	elif texturergb == 'OriginExtents' :
		rgbfunction = ExtentsArray
		hdr = True
	else:
		rgbfunction = rgbnonefuction
	return rgbfunction, hdr


def findalphafunction(texturealpha, hdr):																	# Select the alpha fuction
	if texturealpha == 'Index' :		
		alphafunction = indexarray
		hdr = True
	elif texturealpha == 'Steps' or texturealpha == 'Hierarchyhdr':		#hierarchy is based on level function (later has a second process)
		alphafunction = level
		hdr = True
	elif texturealpha == 'Hierarchy' :
		alphafunction = level
	elif texturealpha == 'Randomhdr' :
		alphafunction = randomfloat
		hdr = True
	elif texturealpha == 'Diameter' :
		alphafunction = diagonal
		hdr = True
	elif texturealpha == 'Xextent' :
		alphafunction = xextent
	elif texturealpha == 'Yextent' :
		alphafunction = yextent
	elif texturealpha == 'Zextent' :
		alphafunction = zextent
	elif texturealpha == 'Random' :
		alphafunction = randomfloat										#the png stores alpha using 0-1 range while 0-256 rgb
	elif texturealpha == 'Diameterscaledhdr' :
		alphafunction = diagonalscaledhdr
		hdr = True
	elif texturealpha == 'Diameterscaled' :
		alphafunction = diagonalscaled
	elif texturealpha == 'SelectionOrder' :
		alphafunction = order
		hdr = True	
	elif texturealpha == 'CustomOrder' :
		alphafunction = customorder
		hdr = True	
	else: alphafunction = alphanonefuction
	return alphafunction, hdr


def createtexture(size,texturenubmer):																		# The Core of the calculations
	pp = bpy.context.scene.pivot_painter
	pixels = [None] * size[0] * size[1]				# RGB pixel list
	hdr = False										# Bool for texture creation
	
	if texturenubmer == 0:				# Select variables between the two textures in the UIPanel
		texturergb = pp.rgb
		texturealpha = pp.alpha
	else: 
		texturergb = pp.rgb2
		texturealpha = pp.alpha2
	
	rgbfunction, hdr = findrgbfunction(texturergb, hdr)					#Texture funtion selection for rgb pixels
	alphafunction, hdr = findalphafunction(texturealpha, hdr)
	
	texturename = texturergb + '_' + texturealpha
	if hdr == True:
		texturename = texturename + '_HDR'

	if pp.createnew == False:
		for img in bpy.data.images:
			if img.name == texturename:
				image = img
	if not 'image'in locals() :
		image = bpy.data.images.new(name=texturename, width=size[0], height=size[1], float_buffer=hdr)
	print(image)
	
	counter = 0															# Counter for loop
	for obj in bpy.context.selected_objects:
		rgbvalues = rgbfunction(pp,obj,counter,size, pixels)			# Does sending unused values affect perfomance(even if minimal)?  There must be a better way. (with the function selection)
		alphavalue = alphafunction(pp,obj,counter,size, pixels)
			
		pixelindex=((size[0]*size[1])-((floor(counter/size[0])+1)*size[0])+(counter%size[0]))
		pixels[pixelindex] = [rgbvalues[0], rgbvalues[1], rgbvalues[2], alphavalue]
		if counter%100 == 0 :
			print (counter, '/' , len(bpy.context.selected_objects), ' texture', texturenubmer +1 )
		counter = counter + 1
		
	for i in range(len(pixels)-1 , 0, -1):								# Fill Empty pixels
		if pixels[i] == None:
			pixels[i] = [1,1,1,1]
			
	if texturealpha == 'Hierarchyhdr' or texturealpha == 'Hierarchy':	# second part of the function to create the hierarchy
		pixels = hierarchy(pp,obj,counter,size, pixels)
	
	# print('Pixels of Texture', texturenubmer+1)
	# print (pixels)
	pixels = [chan for px in pixels for chan in px]						# flatten list # Simple explanation https://stackoverflow.com/questions/37400901/image-flatten-pixel-list
	image.pixels = pixels												# assign pixels
	print('----------------------------------------------------------')


def rgbnonefuction(pp,obj,counter,size, pixels):															# 1 as rgb values , to avoid Null problems (used at the end to fill empty pixels)
	rgb = ( 1, 1, 1)
	return rgb


def alphanonefuction(pp,obj,counter,size, pixels):															# 1 as alpha, to avoid Null problems (used at the end to fill empty pixels)
	a = 1
	return a


def findmaxlevel(pp,obj,counter,size, pixels):																# Highest possible level
	currentlevel = 1											#to avoid /0
	for obj in bpy.context.selected_objects:
		currentlevel = level(pp,obj,counter,size, pixels)
		if currentlevel > maxlevel:
			maxlevel = currentlevel
	return maxlevel


def hierarchy(pp,obj,counter,size, pixels):																	# Hierarchy, current level of the object / highest possible level
	maxlevel = 1
	for i in range(len(pixels)):
		currentlevel = pixels[i][3]
		if currentlevel > maxlevel:
			maxlevel = currentlevel
	for i in range(len(pixels)):
		currentlevel = pixels[i][3]
		normalizedlevel = currentlevel / maxlevel
		pixels[i] = (pixels[i][0], pixels[i][1],pixels[i][2], normalizedlevel)
	return pixels


def order(pp,obj,counter,size, pixels):																		# Selection order using  order by name
	a = counter
	a = packTextureBits(a)
	return a


def customorder(pp,obj,counter,size, pixels):																# Selection order using custom property
	a = obj["SelectionOrder"]											#	Will fail if there is no SelectionOrder property in an selected object.
	a = packTextureBits(a)
	return a


def diagonal(pp,obj,counter,size, pixels):																	# Diagonal length of the bound box
	vec1= mathutils.Vector ((obj.bound_box[0][0], obj.bound_box[0][1], obj.bound_box[0][2] ))				# Vector from the origin point to the min vertex position of the boundbox, unscaled
	vec2= mathutils.Vector ((obj.bound_box[7][0], obj.bound_box[7][1], obj.bound_box[7][2] ))				# Max vertex
	diagonalvector = vec1 + vec2
	length = diagonalvector.length
	return length


def diagonalscaledhdr(pp,obj,counter,size, pixels):															# Diagonal length of the bound box scaled
	ws=obj.matrix_world.to_scale()																							# The scale of the object
	vec1= mathutils.Vector ((obj.bound_box[0][0] * ws[0], obj.bound_box[0][1] * ws[1], obj.bound_box[0][2] * ws[2] ))       # Vector from the origin point to the min vertex position of the boundbox, scaled
	vec2= mathutils.Vector ((obj.bound_box[7][0] * ws[0], obj.bound_box[7][1] * ws[1], obj.bound_box[7][2] * ws[2] ))		# Max vertex
	diagonalvector = vec1 + vec2
	length = diagonalvector.length
	return length


def diagonalscaled(pp,obj,counter,size, pixels):															# Diagonal length of the bound box scaled
	ws=obj.matrix_world.to_scale()																							# The scale of the object
	vec1= mathutils.Vector ((obj.bound_box[0][0] * ws[0], obj.bound_box[0][1] * ws[1], obj.bound_box[0][2] * ws[2] ))       # Vector from the origin point to the min vertex position of the boundbox, scaled
	vec2= mathutils.Vector ((obj.bound_box[7][0] * ws[0], obj.bound_box[7][1] * ws[1], obj.bound_box[7][2] * ws[2] ))		# Max vertex
	diagonalvector = vec1 + vec2
	length = diagonalvector.length
	length = length /8 			
	length = np.clip(length,1,256)
	length = length /256
	return length


def randomfloat(pp,obj,counter,size, pixels):																# Random float
	#a = random.uniform(0, 1)
	a = random.random()
	return a


def ExtentsArray(pp,obj,counter,size, pixels):																# Extents(Dimen) in local coordinates
	r = obj.dimensions[0]
	g = obj.dimensions[1]
	b = obj.dimensions[2]
	rgbvalues = [ r, g, b, ]
	return rgbvalues


def originArray(pp,obj,counter,size, pixels):																# Find the center of the boundbox
	ws=obj.matrix_world.to_scale()																							# The scale of the object
	vec1= mathutils.Vector ((obj.bound_box[0][0] * ws[0], obj.bound_box[0][1] * ws[1], obj.bound_box[0][2] * ws[2] ))       # Vector from the origin point to the min vertex position of the boundbox, scaled
	vec2= mathutils.Vector ((obj.bound_box[7][0] * ws[0], obj.bound_box[7][1] * ws[1], obj.bound_box[7][2] * ws[2] ))		# Max vertex
	center = vec1 + vec2
	center = center /2							# Vector point to Center of the boundbox from origin point in local coordinates

	wr=obj.matrix_world.to_euler('XYZ')			# Rotation of the obj
	center.rotate(wr)
	wl=obj.matrix_world.to_translation()		# Origin positon in global coordinates
	center = center + wl						# The boundbox center in global cordinates
	r = center[0]
	g = center[1]
	b = center[2]
	rgbvalues = [ r, g, b, ]
	return rgbvalues																		# TO DO(maybe): use 3cursor move technic so I can set center type, mass or bb or surface center. (should have minimal cost in performance)


def indexarray(pp,obj,counter,size, pixels):																# Index of the parent. (Uded to inherit properties, like rotation position.)
	if obj.parent:
		index=int(bpy.context.selected_objects.index(obj.parent)) 	# index nubmer of the parent. # do I need remove .5 ? In find object parents it removes from arrayIndex (Line1113 at PivotPainter2.ms)# YES SEE "2dArrayLookupByIndex" material function in the unreal engine. it adds .5
	else:
		index=int(bpy.context.selected_objects.index(obj))
	index = index - 0.5												# Testing # For compatibillity function to be the same as the maxscript. (I have no Idea why this operation ) 
	a = packTextureBits(index)										# packs int to float
	return a


def level(pp,obj,counter,size, pixels):																		# Level, number of parents of every object.
	par=[] 											# Create a list with the parents of the obj
	j = 0
	if obj.parent:
		par.append(obj.parent) 						# First input for while loop. without the first it fails.
		while par[j].parent: 						# IF the parent has a parent    (can it be simplified?)
			par.append(par[j].parent)				# add it to the list
			j=j+1
	level = len(par)
	return level


def pivotarray(pp,obj,counter,size,pixels): 																# Pivot point, in practice the origin positon.
	wl=obj.matrix_world.to_translation()		# Gives world location
	r=wl[0]
	g=-wl[1]
	b=wl[2]
	rgbvalues = [ r, g, b, ]
	return rgbvalues

	
def boundboxAxis(pp,obj,counter,size, pixels):																# Estimates the X vector from the orign point and boundbox vertices. Works only when object has zero rotation.
	bbvv=[]	
	bbLength=[]	
	ws=obj.matrix_world.to_scale()	
	for i in range(8):
		bbvv.append(mathutils.Vector((obj.bound_box[i][0] * ws[0], obj.bound_box[i][1] * ws[1], obj.bound_box[i][2] * ws[2] )))	# Create a vector list for each vert of the bounding box (from origin point)
		bbLength.append(bbvv[i].length)						# Create list with the legths
	
	
	# Find the furthest points from origin (Hopefully they are near the main direction of the object, to use as a xaxis)
	highestVertexId = 0
	for i in range(1,8):										# find the furthest point
		if bbLength[highestVertexId] < bbLength[i]:
			highestVertexId = i
	
	fvidlist = []
	for i in range(8):																						# Check if other vertex have roughlly the same distance
		if bbLength[i] > (bbLength[highestVertexId]-bbLength[highestVertexId]*pp.percentagefreedom/100):			# Give a small range to include similar distances, Blender inconsistencies(from floating values?) and users input
			if bbLength[i] < (bbLength[highestVertexId]+bbLength[highestVertexId]*pp.percentagefreedom/100):
				fvidlist.append(i)
	axisdir = mathutils.Vector((0.0, 0.0, 0.0))
	
	# Get an average position
	for i in range(len(fvidlist)):
		axisdir = bbvv[fvidlist[i]] + axisdir
	axisdir = axisdir /len(fvidlist)
	
	vecout=axisdir.normalized()
	axisextent = axisdir.length
	
	return vecout, axisextent


def xaxisArray(pp,obj,counter,size, pixels):																# X Axis, the direction of the local x axis	
	if pp.firstlevel == True or pp.secondlevel == True or pp.thirdlevel == True or pp.fourthlevel == True :				# Avoid unnecessary calculations. Probably wont use BoundBox method
		localevel = 0
		localevel = level (pp,obj,counter,size, pixels)
		# print (localevel)
		if (localevel == 0 and pp.firstlevel == True) or (localevel == 1 and pp.secondlevel == True) or (localevel == 2 and pp.thirdlevel == True) or (localevel == 3 and pp.fourthlevel == True) :		# Choosing BoundBox method 
			vec, extent = boundboxAxis(pp,obj,counter,size, pixels)
		else:
			vec = mathutils.Vector((1.0, 0.0, 0.0))
			wr=obj.matrix_world.to_euler('XYZ')
			vec.rotate(wr)
	else:
		vec = mathutils.Vector((1.0, 0.0, 0.0))
		wr=obj.matrix_world.to_euler('XYZ')
		vec.rotate(wr)
	r = ( vec[0] +1 ) /2
	g = ( (-vec[1]) +1 ) /2
	b = ( vec[2] +1 ) /2
	rgbvalues = [r, g, b]
	return rgbvalues

def yaxisArray(pp,obj,counter,size, pixels):																# Y Axis, the direction of the local Y axis 
	vec = mathutils.Vector((0.0, 1.0, 0.0))
	wr=obj.matrix_world.to_euler('XYZ')
	vec.rotate(wr)
	r = ( vec[0] +1 ) /2
	g = ( (-vec[1]) +1 ) /2
	b = ( vec[2] +1 ) /2
	rgbvalues = [r, g, b]
	return rgbvalues

def zaxisArray(pp,obj,counter,size, pixels):																# Z Axis, the direction of the local z axis
	vec = mathutils.Vector((0.0, 0.0, 1.0))
	wr=obj.matrix_world.to_euler('XYZ')
	vec.rotate(wr)
	r = ( vec[0] +1 ) /2
	g = ( (-vec[1]) +1 ) /2
	b = ( vec[2] +1 ) /2
	rgbvalues = [r, g, b]
	return rgbvalues

def xextent(pp,obj,counter,size, pixels):																	# X Extent, the length of the object on the local x axis
	if pp.firstlevel == True or pp.secondlevel == True or pp.thirdlevel == True or pp.fourthlevel == True :				# Avoid unnecessary calculations. Probably wont use BoundBox method
		localevel = 0
		localevel = level (pp,obj,counter,size, pixels)
		# print (localevel)
		if (localevel == 0 and pp.firstlevel == True) or (localevel == 1 and pp.secondlevel == True) or (localevel == 2 and pp.thirdlevel == True) or (localevel == 3 and pp.fourthlevel == True) :		# Choosing BoundBox method 
			vec, a = boundboxAxis(pp,obj,counter,size, pixels)
			a = a/8
		else:
			a = obj.dimensions[0]/8 
	else:
		a = obj.dimensions[0]/8 			# "Dimensions" property, chagne with the scale -> There is no need to apply scale, nor does it effect it.
	a = np.clip(a,1,256)
	a = a /256
	return a

def yextent(pp,obj,counter,size, pixels):																	# Y Extent, the length of the object on the local y axis
	objlevel = level(pp,obj,counter,size, pixels)
	a = obj.dimensions[1]/8 			# "Dimensions" property, chagne with the scale -> There is no need to apply scale, nor does it effect it.
	a = np.clip(a,1,256)
	a = a /256
	return a

def zextent(pp,obj,counter,size, pixels):																	# Z Extent, the length of the object on the local z axis
	objlevel = level(pp,obj,counter,size, pixels)
	a = obj.dimensions[2]/8 			# "Dimensions" property, chagne with the scale -> There is no need to apply scale, nor does it effect it.
	a = np.clip(a,1,256)
	a = a /256
	return a


class UE4_PivotPainterProperties(PropertyGroup):															# create property group for user options
	
	totaltextures = IntProperty( name = "Number of Textures", description = "Number of textures to be created.", default = 2, min = 1, max = 8)
	
	alpha_options = [
		("Index", "Index HDR", 'The index number of each part.\nHDR texture needs to be saved as OpenEXR Float(Half).'),
		("Steps", "Number of Steps From Root HDR", 'The level in the hieracrhy.'),
		("Randomhdr", "Random 0-1 Value Per Element HDR", 'Creates a random number per object.'),
		("Diameter", "Bounding Box Diameter HDR", 'The legth of the diagonal of the bound box before scale.'),
		("SelectionOrder", "Selection(Name) Order HDR", 'Blender does not keep track of select order.\nThis will create the order using namer order.'),
		("CustomOrder", "Selection(Custom) Order HDR", 'Blender does not keep track of select order.\nThis will create the order using CUSTOM OBJECT PROPERTY ---> "SelectionOrder".\nUse Create Order property and manually set it for each object.'),
		("Hierarchyhdr", "Normalized 0-1 Hierarchy Position HDR", 'Object number/ Total nubmer of objects.'),
		("Hierarchy", "Normalized 0-1 Hierarchy Position", 'Object number/ Total nubmer of objects.'),
		("Random", "Random 0-1 Value Per Element", 'Creates a random number per object.'),
		("Xextent", "X extent", 'The extent of each object on its local X axis.\nValue source is the X Dimension.'),
		("Yextent", "Y extent", 'The extent of each object on its local Y axis.\nValue source is the Y Dimension.'),
		("Zextent", "Z extent", 'The extent of each object on its local Z axis.\nValue source is the Z Dimension.'),
		("Diameterscaledhdr", "Scaled Bounding Box Diameter HDR", 'The legth of the diagonal of the bound box WITH scale taken into calculation.'),
		("Diameterscaled", "Scaled Bounding Box Diameter", 'The legth of the diagonal of the bound box WITH scale taken into calculation\nValues between 8-2048 in increments of 8.'),
		("None", "None", 'Will use as alpha value 1'),
	]

	rgb_options = [
		("PivotPoint", "Pivot Point HDR", 'The origin point of each object.'),
		("OriginPosition", "Origin Position HDR", 'The bound box center of each objet.'),
		("OriginExtents", "Origin Extents HDR", 'The maximum length of every local axis of each object\nValues source are the object Dimensions.'),
		("Xaxis", "X Axis", 'X Axis from rotation.'),
		("Yaxis", "Y Axis", 'Y Axis from rotation.'),
		("Zaxis", "Z Axis", 'Z Axis from rotation.'),
		("None", "None", 'Will use as rgb values 1')
	]

	
	rgb = bpy.props.EnumProperty( items=rgb_options, name="RGB", description="Select the rgb values", default="PivotPoint") # Any other way to create multiple of them in loop?
	alpha = bpy.props.EnumProperty( items=alpha_options, name="Alpha", description = "Select the alpha values", default="Index" )
	rgb2 = bpy.props.EnumProperty( items=rgb_options, name="RGB", description="Select the rgb values", default="Xaxis" )
	alpha2 = bpy.props.EnumProperty( items=alpha_options, name="Alpha", description = "Select the alpha values", default="Xextent")
	
	automaticindexselect = BoolProperty(name = "Auto UVindex", description = ("Strongly Suggested UNCHECKED and UVIndex 1.\nCreates a new UVMap at the end to use.\nIf there are already 8 UVMaps, will rewrite the last one."))
	uvindex = IntProperty( name="UVIndex", description="UVindex to store the textures coordinates.\nThe Unreal Engine Pivot Painter Tool 2 shaders use UV index 1 by default.\nWill create enought UV maps to reach target.", default=1,	min=0, max=7) # , soft_max=len(obj[0].data.uv_layers) )  # needs to be updated, not worth it		
	
	firstlevel = bpy.props.BoolProperty(name = "1st", description = "For Use with objects that have 0 rotation.\nCalculate the X Axis properties from the BoundBox for the first level.\nOutcome is not very accurate, but should be sufficient.\nVector from origin point and the furthest vertex of the boundingbox.")
	secondlevel = bpy.props.BoolProperty(name = "2nd", description = "For Use with objects that have 0 rotation.\nCalculate the X Axis properties from the BoundBox for the second level.\nOutcome is not very accurate, but should be sufficient.\nVector from origin point and the furthest vertex of the boundingbox.")
	thirdlevel = bpy.props.BoolProperty(name = "3rd", description = "For Use with objects that have 0 rotation.\nCalculate the X Axis properties from the BoundBox for the third level.\nOutcome is not very accurate, but should be sufficient.\nVector from origin point and the furthest vertex of the boundingbox.")
	fourthlevel = bpy.props.BoolProperty(name = "4th", description = "For Use with objects that have 0 rotation.\nCalculate the X Axis properties from the BoundBox for the fourth level.\nOutcome is not very accurate, but should be sufficient.\nVector from origin point and the furthest vertex of the boundingbox.")
	
	percentagefreedom = bpy.props.FloatProperty( name="Additional Percentage", description="Calculates a center point from more vertices of the BoundBox. Percentage of the Max distance, to take additional vertex into account. Default 10%  ", default=10, min=0.00001, soft_min=1, max=50, soft_max=30 )
	createnew = BoolProperty(name = "Always create new textures", default = True, description = ("Should it create a new texture or try overwrite the first one?"))



def main(context):																							# The start of main problem
	print('=============================================================================================================================================================================================')
	t1 = time.time()
	pp = context.scene.pivot_painter 
	size = findTextureDimensions()
	print("Duplicating objects. This may take a moment...") 
	bpy.ops.object.duplicate(linked = True) 					# creates a copy of the objects to work with.
	print ('Time for duplication: ', time.time() - t1)
	createUVMap(size,pp)
	texture1 = 0
	texture2 = 1
	
	# for i in range(pp.totaltextures):			# Dead dreams.....
		# createtexture(size,i)
	createtexture(size,texture1)
	if pp.rgb2 != 'None' and pp.alpha2!= 'None' :
		createtexture(size,texture2)
	print("Joining objects. This will take about twice the time of duplicate operation.")
	t2 = time.time()
	bpy.ops.object.join()
	print ('Time for join operation: ', time.time() - t2)
	print("Done.")
	print("Don't forget to save the textures.")
	print ('Total time: ', time.time() - t1)


class UE4_CreateTexturesOperator(Operator):																	# The button to create the textures
	bl_label = "Create Textures"
	bl_idname = "ue4_tools.create_textures"
	bl_description = "Please have a backup before run.\n The texures need to manually saved (for now).\nDon't mix HDR with LDR in the same texture.\nIf HDR save as OpenEXR, RGBA, Color Depth:Float(Half)\nelse use PNG, RGBA, Color Depth:8\nProgress report in system console for complex projects."
    
	@classmethod
	def poll(cls, context):
			return context.mode == 'OBJECT' # len(context.selected_objects) > 1  and  # and context.active_object.type == 'MESH'		# Check that you are ready to rumble.

	def execute(self, context):
		pp = context.scene.pivot_painter
		units = context.scene.unit_settings
		# noparent = True
		grandparentscount = 0
		for obj in bpy.context.selected_objects:
			# while noparent = true :
			if obj.parent == None :						# Check that there is at least one object with parent 
			#	noparent = False # !=
			# else:
				grandparentscount= grandparentscount +1			# Only 1 object should have no parent (the base)	
		if units.system != 'METRIC' or round(units.scale_length, 2) != 0.01:
			self.report({'ERROR'}, "Scene units must be Metric with a Unit Scale of 0.01!")
			return {'CANCELLED'}
		elif len(context.selected_objects) < 2:
			self.report({'ERROR'}, "Need more Objects!") 
			return {'CANCELLED'}
		# elif len(context.selected_objects) == 1:
		# 	self.report({'ERROR'}, "There is only 1 selected object")
		# 	return {'CANCELLED'}
		elif grandparentscount == 0:
			self.report({'ERROR'}, "Objects have no parent!") 
			return {'CANCELLED'}

		# elif grandparentscount > 1:
		# 	self.report({'ERROR'}, "There are " + str(grandparentscount)+" objects without parent. Should be only 1, the main one.")					# this is wrong. Should be complex objects that have moving parts.Need to check further the script for this function.
		# 	return {'CANCELLED'}
		# elif len(obj.data.uv_layers) < pp.uvindex: 				# Not enough UVlayers
		#	self.report({'ERROR'}, "Not enought UV Maps, select lower UVIndex or Auto") 																# Disabled this to give more freedom, will now create more UV maps
		#	return {'CANCELLED'}
		else:
			main(context)
			return {'FINISHED'}


class UE4_CreateOrderOperator(Operator):																	# Button to create custom property, for 'CustomOrder' type of texture.
	bl_label = "Create custom order property"
	bl_idname = "ue4_tools.create_order"
	bl_description = "Creates a custom property 'SelectionOrder' for all the selected objects.\nFor use with 'Selection(Custom) Order HDR' texure option\nIt is possible for more than 1 objects to have the same order number. eg. In the house demo that blocks will appear together. But maybe will be an empty time in the loop animation, lower the number of objects in the shader to match the animation (or create downtimes in the midlle of the animation?) "
	
	@classmethod
	def poll(cls, context):
			return context.mode == 'OBJECT'		# Check that you are ready to bring order into to haos

	def execute(self, context):
		counter = 1
		for obj in bpy.context.selected_objects:
			obj["SelectionOrder"] = counter
			counter = counter +1
		return {'FINISHED'}


class UE4_PivotPainterPanel(Panel):																			# THe panel in the UI
	bl_idname = "ue4_pivot_painter_panel"
	bl_label = "Pivot Painter"	
	# bl_options = {'REGISTER', 'UNDO'}				
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_category = "Unreal Tools"

  
	def draw(self, context):     						# draw a user interface		(# align = True # use_slider = True # use_pin=true)
		pp = bpy.context.scene.pivot_painter  
		col = self.layout.column()

		col.label(text="1st Texture:")			# I want to draw this with a funtion for x number of textures, but postpone for now, for sanity reasons. # col.prop(pp, "totaltextures")
		col.prop(pp, "rgb")
		col.prop(pp, "alpha")
		col.label(text="2st Texture:")
		col.prop(pp, "rgb2")
		col.prop(pp, "alpha2")
		
		row = self.layout.row()									# Index options
		row.prop(pp, "automaticindexselect")
		sub=row.column()
		if pp.automaticindexselect == True:
			sub.enabled = False
		else:
			sub.enabled = True
		
		sub.prop(pp, "uvindex")
		
		col = self.layout.column()

		
		col = self.layout.column()								# BoundBoxOptions
		col.label(text="Calculate X Axis from BoundBox (Experimental):")
		rows = col.row()
		rows.prop(pp, "firstlevel")
		rows.prop(pp, "secondlevel")
		rows.prop(pp, "thirdlevel")
		rows.prop(pp, "fourthlevel")
		col.prop(pp, "percentagefreedom", slider=True)

		row1 = self.layout.column()	
		row1.scale_y = 1.5
		row1.operator("ue4_tools.create_order")
		row = self.layout.column()	
		row.prop(pp, "createnew")

		
		row = self.layout.row()
		row.scale_y = 2
		row.operator("ue4_tools.create_textures")
		# row.operator("test")


def register():																								# Register function to add the script
	bpy.utils.register_class(UE4_PivotPainterPanel)
	bpy.utils.register_class(UE4_CreateOrderOperator)
	bpy.utils.register_class(UE4_CreateTexturesOperator)
	bpy.utils.register_class(UE4_PivotPainterProperties)
	bpy.types.Scene.pivot_painter = PointerProperty(type = UE4_PivotPainterProperties)

def unregister():																							# Register function to add the script
	bpy.utils.unregister_class(UE4_PivotPainterPanel)
	bpy.utils.unregister_class(UE4_CreateOrderOperator)
	bpy.utils.unregister_class(UE4_CreateTexturesOperator)
	bpy.utils.unregister_class(UE4_PivotPainterProperties)
	del bpy.types.Scene.pivot_painter
    
if __name__ == "__main__":																					# For manual execution(testing)
 	register()