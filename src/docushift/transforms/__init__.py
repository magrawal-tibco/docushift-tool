"""Engine-neutral GFM transforms.

Pure functions over parsed HTML and over paths. Nothing here opens a file, and no
engine imports another engine to reach any of it -- which is what keeps the rules
that are shared (`design.md` §6.4's asset resolution, §9's CSH schema, the GFM
alert vocabulary) one rule rather than four copies of it.
"""
