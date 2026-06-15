resource "aws_s3_bucket" "raw_data_lake" {
  bucket = "${var.project_name}-${var.environment}-raw-data-lake"
}

resource "aws_s3_bucket_lifecycle_configuration" "lake_lifecycle" {
  bucket = aws_s3_bucket.raw_data_lake.id

  rule {
    id     = "archive"
    status = "Enabled"

    filter {}

    transition {
      days          = 30
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }
}

resource "aws_s3_bucket_public_access_block" "lake_access" {
  bucket = aws_s3_bucket.raw_data_lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
