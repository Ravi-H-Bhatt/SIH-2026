Drop face images here to test biometric matching from the terminal.

I could not test the two photos you pasted into chat directly — chat
attachments are not files on disk, so I have no way to read them. Save them
into this folder and run:

    cd backend
    ./venv/bin/python verify_face_matching.py

The script prints the full pairwise raw-cosine matrix for every image it finds
here (and in uploads/), plus a SAME_PERSON / DIFFERENT verdict against the
0.363 threshold.

To compare exactly two specific files:

    ./venv/bin/python -c "
    from app.services.face.face_service import face_service
    import json
    print(json.dumps(face_service.compare_two_images(
        'verify_images/photo1.jpg',
        'verify_images/photo2.jpg'), indent=2))
    "

Or use the UI: Biometric Identification -> '1:1 Compare two images'.

Expected result for your two photos: they are visibly two different people,
so the cosine should land well below 0.363 and the verdict should read
DIFFERENT_PERSON. Before the fix, any cosine above 0.30 was stretched onto
[0.70, 0.99] and reported as a pass, which is why unrelated faces "matched".
