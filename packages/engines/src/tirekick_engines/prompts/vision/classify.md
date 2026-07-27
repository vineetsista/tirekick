---
id: classify
version: 1
---
Classify this photograph of a vehicle into exactly one view category.

The categories are:

- `exterior_front`, `exterior_rear`, `exterior_side_left`, `exterior_side_right`,
  `exterior_three_quarter` - the outside of the car, named by which side faces the
  camera
- `interior_front`, `interior_rear` - the cabin
- `engine_bay` - the bonnet is open and the engine is visible
- `odometer` - the mileage reading is the subject of the photograph
- `dash` - the instrument cluster, whether or not lamps are lit
- `tire` - a wheel or tire is the subject
- `vin_plate` - a VIN plate or door-jamb sticker
- `document` - paperwork, a title, a service record
- `undercarriage` - taken from underneath the vehicle
- `unknown` - anything else, or anything you are not sure about

Answer `unknown` when the photograph does not clearly show one of these. A wrong
classification sends the wrong analysis at the image, and a wrong analysis is
worse than no analysis: it produces confident findings about the wrong part of the
car. Being unsure is cheap here. Being wrong is not.

Report the category and your confidence in it.
