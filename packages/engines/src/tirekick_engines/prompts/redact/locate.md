---
id: locate
version: 1
---
Find every region in this photograph that must be hidden before publication.

For each one, give a bounding box in normalized coordinates - x and y are the
top-left corner, all four values between 0 and 1 - and say which kind it is:

- `plate` - a vehicle number plate, on any vehicle, including partial and
  reflected ones
- `face` - a human face, at any size, including in the background or a mirror
- `vin` - a VIN plate or door-jamb sticker showing the full number
- `document_id` - paperwork showing a name, address, or identification number
- `other` - anything else identifying: a house number, a street sign that pins the
  location, a business name on a van

Add a short note saying where in the frame it is, so the person reviewing your
output can find it without hunting.

Box generously. A tight box around a plate clips a character, and a plate missing
one character is still a plate somebody can read.
