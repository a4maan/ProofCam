"""Generate a dependency-free Xcode project; stable IDs keep diffs reviewable."""
from pathlib import Path
import hashlib
root = Path(__file__).resolve().parents[1]
def ident(s): return hashlib.sha256(s.encode()).hexdigest()[:24].upper()
objects = {}
def add(name, body): objects[ident(name)] = '{ ' + body + ' };'; return ident(name)
files=[]; builds=[]
for path in ['ProofCamResearch/App.swift', 'ProofCamResearch/CaptureProvenance.swift', 'ProofCamResearch/AppAttestProvenance.swift', 'Core/Sources/ProofCamCore/ProvenanceWire.swift', 'Core/Sources/ProofCamCore/Watermark.swift', 'Core/Sources/ProofCamCore/ResearchUtilities.swift', 'Core/Sources/ProofCamCore/AppleImageCodec.swift', 'Core/Sources/ProofCamCore/TiledCandidate.swift', 'Core/Sources/ProofCamCore/AdaptiveCandidate.swift', 'Core/Sources/ProofCamCore/GrayPlane.swift']:
    f=add(path, f'isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = "{path}"; sourceTree = "<group>";')
    files.append(f); builds.append(add('build'+path, f'isa = PBXBuildFile; fileRef = {f};'))
product=add('product','isa = PBXFileReference; explicitFileType = wrapper.application; path = ProofCamResearch.app; sourceTree = BUILT_PRODUCTS_DIR;')
products=add('products',f'isa = PBXGroup; children = ({product},); name = Products; sourceTree = "<group>";')
group=add('group',f'isa = PBXGroup; children = ({",".join(files+[products])},); sourceTree = "<group>";')
sources=add('sources',f'isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = ({",".join(builds)},); runOnlyForDeploymentPostprocessing = 0;')
frameworks=add('frameworks','isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0;')
configs={}
for scope in ['project','target']:
    ids=[]
    for mode in ['Debug','Release']:
        settings='IPHONEOS_DEPLOYMENT_TARGET = 17.0; SDKROOT = iphoneos; SWIFT_VERSION = 5.0; CLANG_ENABLE_MODULES = YES; '
        settings += 'SWIFT_OPTIMIZATION_LEVEL = "-O"; ' if mode=='Release' else 'SWIFT_OPTIMIZATION_LEVEL = "-Onone"; '
        if scope=='target': settings+='PROOFCAM_APP_ATTEST_ENABLED = NO; PROOFCAM_APP_ATTEST_ENTITLEMENTS = ""; INFOPLIST_KEY_ProofCamAppAttestEnabled = "$(PROOFCAM_APP_ATTEST_ENABLED)"; CODE_SIGN_ENTITLEMENTS = "$(PROOFCAM_APP_ATTEST_ENTITLEMENTS)"; PRODUCT_NAME = "$(TARGET_NAME)"; PRODUCT_BUNDLE_IDENTIFIER = com.a4maan.proofcam.research; GENERATE_INFOPLIST_FILE = YES; INFOPLIST_KEY_CFBundleDisplayName = "ProofCam Research"; INFOPLIST_KEY_NSCameraUsageDescription = "Take a photo and bind its final export to a device-signed development request."; INFOPLIST_KEY_UILaunchScreen_Generation = YES; INFOPLIST_KEY_UIApplicationSceneManifest_Generation = YES; INFOPLIST_KEY_UISupportedInterfaceOrientations = UIInterfaceOrientationPortrait; TARGETED_DEVICE_FAMILY = 1; CODE_SIGN_STYLE = Automatic; CURRENT_PROJECT_VERSION = 1; MARKETING_VERSION = 0.1; SUPPORTED_PLATFORMS = "iphoneos iphonesimulator"; '
        ids.append(add(scope+mode,f'isa = XCBuildConfiguration; buildSettings = {{ {settings} }}; name = {mode};'))
    configs[scope]=add(scope+'configs',f'isa = XCConfigurationList; buildConfigurations = ({",".join(ids)},); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;')
target=add('target',f'isa = PBXNativeTarget; buildConfigurationList = {configs["target"]}; buildPhases = ({sources},{frameworks},); buildRules = (); dependencies = (); name = ProofCamResearch; productName = ProofCamResearch; productReference = {product}; productType = "com.apple.product-type.application";')
project=add('project',f'isa = PBXProject; attributes = {{ LastUpgradeCheck = 1600; }}; buildConfigurationList = {configs["project"]}; compatibilityVersion = "Xcode 14.0"; developmentRegion = en; hasScannedForEncodings = 0; knownRegions = (en,Base,); mainGroup = {group}; productRefGroup = {products}; projectDirPath = ""; projectRoot = ""; targets = ({target},);')
folder=root/'ProofCamResearch.xcodeproj'; folder.mkdir(exist_ok=True)
(folder/'project.pbxproj').write_text('// !$*UTF8*$!\n{ archiveVersion = 1; classes = {}; objectVersion = 56; objects = {\n'+ '\n'.join(k+' = '+v for k,v in objects.items())+'\n}; rootObject = '+project+'; }\n')
schemes=folder/'xcshareddata/xcschemes'; schemes.mkdir(parents=True,exist_ok=True)
ref=f'<BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{target}" BuildableName="ProofCamResearch.app" BlueprintName="ProofCamResearch" ReferencedContainer="container:ProofCamResearch.xcodeproj"/>'
(schemes/'ProofCamResearch.xcscheme').write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="1600" version="1.3"><BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries><BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES">{ref}</BuildActionEntry></BuildActionEntries></BuildAction><LaunchAction buildConfiguration="Release" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" debugServiceExtension="internal" allowLocationSimulation="YES"><BuildableProductRunnable runnableDebuggingMode="0">{ref}</BuildableProductRunnable></LaunchAction><ProfileAction buildConfiguration="Release" shouldUseLaunchSchemeArgsEnv="YES" savedToolIdentifier="" useCustomWorkingDirectory="NO" debugDocumentVersioning="YES"><BuildableProductRunnable runnableDebuggingMode="0">{ref}</BuildableProductRunnable></ProfileAction><AnalyzeAction buildConfiguration="Debug"/><ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/></Scheme>''')
