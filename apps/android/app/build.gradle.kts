plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// factcheck-core through uniffi: the .so files and their Kotlin bindings.
val rustOut = layout.buildDirectory.dir("generated/rust")
val buildBridge = tasks.register<Exec>("buildBridge") {
    workingDir = rootDir.resolve("bridge")
    commandLine("./build-android.sh", rustOut.get().asFile.path)
}
tasks.named("preBuild") { dependsOn(buildBridge) }

android {
    namespace = "digital.quebracho.lapacho.plugin.factcheck"
    compileSdk = 35

    defaultConfig {
        applicationId = "digital.quebracho.lapacho.plugin.factcheck"
        minSdk = 28
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
    }

    // Same key as Lapacho's published APKs when it's given; debug key otherwise.
    signingConfigs {
        System.getenv("LAPACHO_RELEASE_KEYSTORE")?.let { path ->
            create("release") {
                storeFile = file(path)
                storePassword = System.getenv("LAPACHO_RELEASE_KEYSTORE_PASSWORD")
                keyAlias = "lapacho"
                keyPassword = storePassword
            }
        }
    }
    buildTypes {
        getByName("release") {
            signingConfig = signingConfigs.findByName("release") ?: signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    sourceSets["main"].jniLibs.srcDir(rustOut.map { it.dir("jniLibs") })
    sourceSets["main"].java.srcDir(rustOut.map { it.dir("kotlin") })
    sourceSets["main"].assets.srcDir("../../../examples")
}

dependencies {
    // uniffi's Kotlin bindings load the .so through JNA.
    implementation("net.java.dev.jna:jna:5.14.0@aar")
}
