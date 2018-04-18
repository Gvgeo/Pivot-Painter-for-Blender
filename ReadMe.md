# Pivot Painter for Blender

Pivot Painter is a Blender addon to create a 3d model, for use with Pivot Painter Tool's shaders in Unreal Engine 4

## Getting Started

The addon tries to mimic the basic funtion of the 3dsmaxscript that is based on, while missing many tools that would speed up the creation of a final mesh. As such the resulting mesh and texture, should be fully compatible with the build in material functions of the Pivot Painter Tool 2 shader. Therefore should refer to unreal engine documentation for [Pivot Painter Tool 2.0](https://docs.unrealengine.com/en-us/Engine/Content/Tools/PivotPainter)

The main order of operations is:
* duplication of the selected objects
* Creation of the textures
* join of the duplicate objects to a final mesh

### Installing

* Download Zip file
* open up Blender
* go to: File -> User Preferences -> Addons -> Install Add-on from File...
* select the ZIP you downloaded and click install from file
* activate the addon from user preferences

### Prerequisites

The addon to work, needs all the parts of the mesh to be seperate objects, and necessary settings configed depending of the texture selection.

E.g. to create a tree you need to set prior the parent of each object and the origin point,  while to recreate the house(from the content examples) you need to set the selection order.

### Examples
A .blend file is included with two examles.
Both examples need 2 Textures.

The Tree from cubes needs:
* Pivot point HDR and Index HDR
* X Axis and X extent

The House on layer 2 needs:
* X Axis and Random (8bit not HDR)
* Pivot Point HDR and Selection Order(Custom)

Select all the objects of the mesh you want to create and press Create Texture.

See info on Create Texture button for save format.

Use the mesh and textures to see the result in Unreal Engine.

## Considerations
Because the tool requires separate objects to work, in complex meshes the number of meshes can be heavily impact the performance of the Blender UI.

## Current State
While the tool can already be used to create the desired effect, it is mainly untested and problems or inaccuracies may occur. 
Also... expect crashes.

## Author

 *George Vogiatzis*

## License

This project is Licensed under the EUPL- see the [LICENSE.txt](LICENSE.txt) file for details

## Acknowledgment

* This addon is based on the 3dsMaxScript Pivot Painter version 2.0 written by Jonathan Lindquist at Epic Games

