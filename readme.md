Adds DMX512 support to blender using the Art-Net protocol. The received values can be used in driver expressions or in custom python code anywhere in blender!

# Usage

After installing and activating the Addon, you can activate the Art-Net
receiver using the panel in the Properties -> Scene tab.

You can then use the received dmx values on any property that supports a driver
expression by using the following two added driver functions:

`#dmx(channel)` -> 0 - 255 (raw integer output)\
`#dmxf(channel)` -> 0.0 - 1.0 (normalized float output)

**Please Note**:
Driver evaluation is controlled by blender, you typically have to play the
timeline to trigger blender to update the driver expressions.

## Examples

For example to control the intensity of a light with your first dmx channel
between 0W and 300W you can use `#dmxf(0) * 300` in its power field.

To move an object up and down by 5m with your second dmx channel use `#(2*dmxf(1) - 1) * 5` in its z-location field.

To rotate an object around the z axis from 0° to 255° with your third dmx channel use `#dmx(2)` in its z-rotation field.


## For Python Scripters
You can also use the driver namespace function to use the received values in your advanced python scripts:

```python
>>> bpy.app.driver_namespace['dmx'](0)
149

>>> bpy.app.driver_namespace['dmxf'](0)
0.5843137254901961
```
