# RRExporter
This is vibecoded btw

It downloads your rooms, and misc data (like holotars/samplers) and saves them to a local folder. It also downloads all of your past saves as well.

Get your Authorization token from RecNet first. You can easily do that by opening inspect element on the RecNet website, going to the network tab, and looking for requests like `/account/me`. The Authorization token will be in the headers of that request.

Next, get a JSON array of rooms you want to export. I just downloaded the response of `ownedby/me`(?) with HTTP debugger on rec room.

Then just run the script with the arguments --token and --json and everything will be downloaded.

>[!WARNING]
> I don't know how to decode the protobuf to get the exact string when downloading misc data, so I just check for .htr, .jpg, .png. So check for errors downloading files in the console!