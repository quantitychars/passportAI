# PassportAI S3 Setup

This step makes generated DPP artifacts publicly accessible from AWS S3:

```text
passport.json
passport.html
gap_report.html
product_image.jpg
```

QR generation comes later. QR must point to the public `passport.html` URL produced by storage.

## 1. What this implementation does

`src/storage/aws_s3.py` uploads local generated artifacts to S3 and returns a stable public URL.

Default object layout:

```text
s3://<bucket>/passports/<passport_id>/passport.html
s3://<bucket>/passports/<passport_id>/passport.json
s3://<bucket>/passports/<passport_id>/gap_report.html
s3://<bucket>/passports/<passport_id>/product_image.jpg
```

Public URL examples:

```text
https://<bucket>.s3.eu-west-1.amazonaws.com/passports/<passport_id>/passport.html
https://<cloudfront-domain>/passports/<passport_id>/passport.html
```

## 2. Install dependencies

```cmd
pip install -r requirements.txt
```

`boto3` is already listed in `requirements.txt`.

## 3. Create a dedicated S3 bucket

Use a dedicated bucket for the demo, not a personal mixed-use bucket.

Recommended region for the project:

```text
eu-west-1
```

Example bucket name:

```text
passportai-demo-yourname
```

## 4. Public access model

For the contest demo, the generated `passport.html` must be openable by judges.

Recommended simple demo setup:

1. Create a dedicated bucket.
2. Allow public read for generated passport objects.
3. Keep write permissions restricted to your IAM user/role.
4. Use `PUBLIC_BASE_URL` if you use CloudFront or a custom domain.

AWS documents that public static website/object access requires changing Block Public Access settings and adding a bucket policy that grants `s3:GetObject`; public read means anyone on the internet can access those objects.

## 5. Bucket policy for public read

Replace `passportai-demo-yourname` with your bucket name.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PassportAIPublicRead",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::passportai-demo-yourname/passports/*"
    }
  ]
}
```

This grants public read only under the `passports/` prefix.

Do not grant public write.

## 6. IAM permissions for upload

Use least privilege. For local development, avoid root account keys. AWS recommends temporary credentials such as IAM roles where possible; if you use access keys, create them for a limited IAM user, not the root account.

Minimal write policy for your uploader IAM user/role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PassportAIListPrefix",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::passportai-demo-yourname",
      "Condition": {
        "StringLike": {
          "s3:prefix": ["passports/*"]
        }
      }
    },
    {
      "Sid": "PassportAIWriteObjects",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::passportai-demo-yourname/passports/*"
    }
  ]
}
```

## 7. Configure `.env`

Copy `.env.example` to `.env` and set:

```env
STORAGE_MODE=s3
AWS_REGION=eu-west-1
AWS_S3_BUCKET=passportai-demo-yourname
AWS_S3_PREFIX=passports

# Use this if you have CloudFront/custom domain:
PUBLIC_BASE_URL=https://your-cloudfront-or-domain.example.com

# Otherwise leave it empty and S3Storage will use:
# https://<bucket>.s3.<region>.amazonaws.com/<key>
PUBLIC_BASE_URL=
```

Credentials options:

### Option A — AWS CLI profile / default credentials

```cmd
aws configure
```

Then leave these empty in `.env`:

```env
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SESSION_TOKEN=
```

### Option B — environment variables for local demo only

```env
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_SESSION_TOKEN=...
```

Do not commit `.env`.

## 8. Smoke test from Python

```cmd
python - <<PY
from pathlib import Path
from src.storage.aws_s3 import S3Storage

tmp = Path("s3_smoke_test.html")
tmp.write_text("<h1>PassportAI S3 smoke test</h1>", encoding="utf-8")

storage = S3Storage()
url = storage.save_package("smoke-test", {"passport.html": tmp})

print(url)
print(storage.file_exists("smoke-test", "passport.html"))

tmp.unlink()
PY
```

Open the printed URL in a browser.

## 9. Expected failure modes

### `AWS_S3_BUCKET must be set`

Set `AWS_S3_BUCKET` in `.env` or pass `bucket=...`.

### `AccessDenied`

Your IAM user/role does not have `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`, or `s3:ListBucket` for the selected prefix.

### Browser downloads HTML instead of rendering it

Wrong `Content-Type`. This implementation uploads `passport.html` as:

```text
text/html; charset=utf-8
```

### URL returns 403

The object uploaded, but public read is not configured. Add a public read bucket policy for `passports/*` or put CloudFront in front of the bucket.

## 10. Why QR is not part of this block

QR must be generated only after this works:

```python
storage.get_public_url(passport_id, "passport.html")
```

Otherwise QR would point to localhost or a temporary URL and would need to be regenerated.
