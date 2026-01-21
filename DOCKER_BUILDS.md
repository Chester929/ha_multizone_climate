# Multi-architecture Docker Builds

This repository uses GitHub Actions to automatically build and push multi-architecture Docker images to GitHub Container Registry (GHCR) for the Logic container.

## Supported Architectures

The Logic container image supports the following architectures:
- **linux/amd64** (x86_64) - Standard desktop/server systems
- **linux/arm/v7** (armv7) - 32-bit ARM devices (e.g., Raspberry Pi 2/3)
- **linux/arm64** (aarch64) - 64-bit ARM devices (e.g., Raspberry Pi 4, Apple Silicon)

## Container Image

The following image is built and published:

| Component | Image Name | Description |
|-----------|------------|-------------|
| Logic Container | `ghcr.io/chester929/multizone-logic` | Core business logic (GoLang) |

**Note:** Redis uses the official Redis image from Docker Hub, which already provides multi-architecture support.

## Image Tags

Images are automatically tagged based on the trigger:

### Branch Builds
- `master` → `latest` tag
- `dev` → `dev` tag
- Other branches → `<branch-name>` tag

### Pull Requests
- Pull requests → `pr-<number>` tag (build only, not pushed)

### Version Tags
When you create a Git tag with semantic versioning (e.g., `v1.2.3`):
- `v1.2.3` → `1.2.3`, `1.2`, `1`, `latest`

### Commit SHA
All builds include a tag with the commit SHA:
- `<branch>-<sha>` (e.g., `master-abc1234`)

## Usage

### Pull Latest Image

```bash
docker pull ghcr.io/chester929/multizone-logic:latest
```

### Pull Specific Version

```bash
docker pull ghcr.io/chester929/multizone-logic:1.2.3
docker pull ghcr.io/chester929/multizone-logic:1.2
docker pull ghcr.io/chester929/multizone-logic:1
```

### Use in Docker Compose

See `docker-compose.ghcr.yml` for an example configuration that uses pre-built images.

## GitHub Actions Workflow

The workflow (`.github/workflows/docker-multiarch.yml`) is triggered by:
- **Push to master/dev branches**: Builds and pushes images
- **Version tags** (v*): Builds and pushes with semantic version tags
- **Pull requests**: Builds images for validation (doesn't push)
- **Manual trigger**: Via workflow_dispatch

### Build Process

1. **Checkout code**: Gets the repository code
2. **Set up QEMU**: Enables multi-architecture emulation
3. **Set up Docker Buildx**: Enables advanced Docker build features
4. **Login to GHCR**: Authenticates with GitHub Container Registry
5. **Extract metadata**: Generates appropriate tags based on trigger
6. **Build and push**: Builds for all architectures and pushes to GHCR
7. **Generate summary**: Creates a build summary in the Actions UI

### Build Features

- **Build caching**: GitHub Actions cache speeds up subsequent builds
- **Multi-platform**: Single command builds all architectures
- **Automatic tagging**: Smart tag generation based on Git context

## Permissions

The workflow requires the following permissions:
- `contents: read` - To checkout the repository
- `packages: write` - To push images to GHCR

These are automatically provided by `GITHUB_TOKEN`.

## Manual Trigger

You can manually trigger a build:
1. Go to the "Actions" tab in GitHub
2. Select "Multi-architecture Docker Build"
3. Click "Run workflow"
4. Select the branch and click "Run workflow"

## Viewing Build Results

After a successful build:
1. Go to the repository's "Packages" section
2. Click on a package (e.g., `multizone-logic`)
3. You'll see all available tags and architectures
4. Each manifest shows the supported platforms

## Local Multi-architecture Build

To build multi-architecture images locally:

```bash
# Set up buildx builder
docker buildx create --name multiarch --use

# Build for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm/v7,linux/arm64 \
  -t ghcr.io/chester929/multizone-logic:test \
  --load ./logic

# Or push directly to registry
docker buildx build \
  --platform linux/amd64,linux/arm/v7,linux/arm64 \
  -t ghcr.io/chester929/multizone-logic:test \
  --push ./logic
```

Note: You need to authenticate with GHCR first:
```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
```

## Troubleshooting

### Image not found
- Check that the image name is correct (lowercase only)
- Verify the tag exists in the package registry
- For private repos, ensure you're authenticated

### Architecture not supported
- Verify your platform with: `docker version --format '{{.Server.Arch}}'`
- Check the manifest: `docker manifest inspect ghcr.io/chester929/multizone-logic:latest`

### Build failures
- Check the Actions logs for error messages
- Common issues: Dockerfile syntax, missing dependencies, build context problems
- Test locally first with: `docker build ./logic`

## Security

- Images are scanned for vulnerabilities (if enabled)
- Use specific version tags in production, not `latest`
- Regularly update base images in Dockerfiles
- Review security advisories for dependencies

## Related Documentation

- [GitHub Container Registry Docs](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Docker Buildx Documentation](https://docs.docker.com/buildx/working-with-buildx/)
- [Docker Multi-platform Images](https://docs.docker.com/build/building/multi-platform/)
