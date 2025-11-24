-- MariaDB dump 10.19  Distrib 10.4.32-MariaDB, for Win64 (AMD64)
--
-- Host: localhost    Database: db_sistem_pos_v30
-- ------------------------------------------------------
-- Server version	10.4.32-MariaDB

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `booking_event`
--

DROP TABLE IF EXISTS `booking_event`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `booking_event` (
  `id_booking_event` bigint(20) NOT NULL AUTO_INCREMENT,
  `id_event_space` int(11) NOT NULL,
  `id_user` int(11) DEFAULT NULL COMMENT 'NULL jika guest',
  `id_transaksi` bigint(20) NOT NULL,
  `tanggal_event` date NOT NULL,
  `waktu_mulai` datetime NOT NULL,
  `waktu_selesai` datetime NOT NULL,
  `status_booking` enum('Baru','Confirmed','Selesai','Dibatalkan') NOT NULL DEFAULT 'Baru',
  `nama_acara` varchar(255) NOT NULL,
  `deskripsi` text DEFAULT NULL,
  `jumlah_peserta` int(11) DEFAULT NULL,
  `kebutuhan_tambahan` text DEFAULT NULL,
  `alasan_pembatalan` text DEFAULT NULL,
  PRIMARY KEY (`id_booking_event`),
  KEY `id_event_space` (`id_event_space`),
  KEY `id_user` (`id_user`),
  KEY `id_transaksi` (`id_transaksi`),
  CONSTRAINT `booking_event_ibfk_1` FOREIGN KEY (`id_event_space`) REFERENCES `event_spaces` (`id_event_space`) ON DELETE CASCADE,
  CONSTRAINT `booking_event_ibfk_2` FOREIGN KEY (`id_user`) REFERENCES `users` (`id_user`) ON DELETE SET NULL,
  CONSTRAINT `booking_event_ibfk_3` FOREIGN KEY (`id_transaksi`) REFERENCES `transaksi` (`id_transaksi`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `booking_event`
--

LOCK TABLES `booking_event` WRITE;
/*!40000 ALTER TABLE `booking_event` DISABLE KEYS */;
/*!40000 ALTER TABLE `booking_event` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `booking_ruangan`
--

DROP TABLE IF EXISTS `booking_ruangan`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `booking_ruangan` (
  `id_booking` bigint(20) NOT NULL AUTO_INCREMENT,
  `id_transaksi` bigint(20) NOT NULL,
  `id_ruangan` int(11) NOT NULL,
  `id_memberships` int(11) DEFAULT NULL COMMENT 'Diisi jika booking menggunakan kredit',
  `waktu_mulai` datetime NOT NULL,
  `waktu_selesai` datetime NOT NULL,
  `durasi` int(11) NOT NULL COMMENT 'Durasi dalam menit',
  `harga_saat_booking` int(11) NOT NULL DEFAULT 0,
  `kredit_terpakai` int(11) DEFAULT 0,
  PRIMARY KEY (`id_booking`),
  UNIQUE KEY `unique_booking` (`id_ruangan`,`waktu_mulai`,`waktu_selesai`),
  KEY `id_transaksi` (`id_transaksi`),
  KEY `id_ruangan` (`id_ruangan`),
  KEY `id_memberships` (`id_memberships`),
  CONSTRAINT `booking_ruangan_ibfk_1` FOREIGN KEY (`id_transaksi`) REFERENCES `transaksi` (`id_transaksi`) ON DELETE CASCADE,
  CONSTRAINT `booking_ruangan_ibfk_2` FOREIGN KEY (`id_ruangan`) REFERENCES `ruangan` (`id_ruangan`),
  CONSTRAINT `booking_ruangan_ibfk_3` FOREIGN KEY (`id_memberships`) REFERENCES `memberships` (`id_memberships`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `booking_ruangan`
--

LOCK TABLES `booking_ruangan` WRITE;
/*!40000 ALTER TABLE `booking_ruangan` DISABLE KEYS */;
INSERT INTO `booking_ruangan` VALUES (1,1,4,NULL,'2025-11-15 08:00:00','2025-11-15 10:00:00',2,0,0),(2,2,1,NULL,'2025-11-14 15:00:00','2025-11-14 17:00:00',120,0,0),(3,3,26,NULL,'2025-11-18 08:00:00','2025-11-18 10:00:00',2,0,0),(4,10,1,NULL,'2025-11-18 15:00:00','2025-11-18 17:00:00',120,0,0),(5,11,15,NULL,'2025-11-18 15:00:00','2025-11-18 17:00:00',120,0,0),(7,12,16,NULL,'2025-11-18 15:00:00','2025-11-18 17:00:00',120,20000,0);
/*!40000 ALTER TABLE `booking_ruangan` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chart_of_accounts`
--

DROP TABLE IF EXISTS `chart_of_accounts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `chart_of_accounts` (
  `id_coa` int(11) NOT NULL AUTO_INCREMENT,
  `kode_akun` varchar(50) NOT NULL,
  `nama_akun` varchar(255) NOT NULL,
  `tipe_akun` enum('Aset','Liabilitas','Ekuitas','Pendapatan','HPP','Beban') NOT NULL,
  `deskripsi` text DEFAULT NULL,
  PRIMARY KEY (`id_coa`),
  UNIQUE KEY `idx_kode_akun_unik` (`kode_akun`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chart_of_accounts`
--

LOCK TABLES `chart_of_accounts` WRITE;
/*!40000 ALTER TABLE `chart_of_accounts` DISABLE KEYS */;
INSERT INTO `chart_of_accounts` VALUES (1,'5','Pendapatan F&B','Pendapatan',NULL);
/*!40000 ALTER TABLE `chart_of_accounts` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `client_virtual_office`
--

DROP TABLE IF EXISTS `client_virtual_office`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `client_virtual_office` (
  `id_client_vo` int(11) NOT NULL AUTO_INCREMENT,
  `id_user` int(11) NOT NULL,
  `id_paket_vo` int(11) NOT NULL,
  `id_transaksi` bigint(20) NOT NULL,
  `nama` text DEFAULT NULL,
  `jabatan` text DEFAULT NULL,
  `nama_perusahaan_klien` varchar(255) NOT NULL,
  `bidang_perusahaan` text DEFAULT NULL,
  `alamat_perusahaan` text DEFAULT NULL,
  `email_perusahaan` text DEFAULT NULL,
  `alamat_domisili` text DEFAULT NULL,
  `nomor_telepon` int(11) DEFAULT NULL,
  `tanggal_mulai` date DEFAULT NULL,
  `tanggal_berakhir` date DEFAULT NULL,
  `status_client_vo` enum('Menunggu Persetujuan','Menunggu Pembayaran','Aktif','Ditolak','Kadaluarsa') NOT NULL DEFAULT 'Menunggu Persetujuan',
  `doc_path` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id_client_vo`),
  KEY `id_user` (`id_user`),
  KEY `id_paket_vo` (`id_paket_vo`),
  KEY `id_transaksi` (`id_transaksi`),
  CONSTRAINT `client_virtual_office_ibfk_1` FOREIGN KEY (`id_user`) REFERENCES `users` (`id_user`) ON DELETE CASCADE,
  CONSTRAINT `client_virtual_office_ibfk_2` FOREIGN KEY (`id_paket_vo`) REFERENCES `paket_virtual_office` (`id_paket_vo`),
  CONSTRAINT `client_virtual_office_ibfk_3` FOREIGN KEY (`id_transaksi`) REFERENCES `transaksi` (`id_transaksi`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `client_virtual_office`
--

LOCK TABLES `client_virtual_office` WRITE;
/*!40000 ALTER TABLE `client_virtual_office` DISABLE KEYS */;
/*!40000 ALTER TABLE `client_virtual_office` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `detail_order_fnb`
--

DROP TABLE IF EXISTS `detail_order_fnb`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `detail_order_fnb` (
  `id_detail_order` bigint(20) NOT NULL AUTO_INCREMENT,
  `id_transaksi` bigint(20) NOT NULL,
  `id_produk` int(11) NOT NULL,
  `jumlah` int(11) NOT NULL,
  `harga_saat_order` int(11) NOT NULL,
  `catatan_pesanan` text DEFAULT NULL,
  `status_pesanan` enum('Baru','Diproses','Selesai','Batal') NOT NULL DEFAULT 'Baru',
  PRIMARY KEY (`id_detail_order`),
  KEY `id_transaksi` (`id_transaksi`),
  KEY `id_produk` (`id_produk`),
  CONSTRAINT `detail_order_fnb_ibfk_1` FOREIGN KEY (`id_transaksi`) REFERENCES `transaksi` (`id_transaksi`) ON DELETE CASCADE,
  CONSTRAINT `detail_order_fnb_ibfk_2` FOREIGN KEY (`id_produk`) REFERENCES `produk_fnb` (`id_produk`)
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `detail_order_fnb`
--

LOCK TABLES `detail_order_fnb` WRITE;
/*!40000 ALTER TABLE `detail_order_fnb` DISABLE KEYS */;
INSERT INTO `detail_order_fnb` VALUES (1,2,69,1,15000,NULL,'Baru'),(2,5,68,1,15000,NULL,'Baru'),(3,6,68,1,15000,NULL,'Baru'),(4,7,68,1,15000,NULL,'Baru'),(5,8,68,1,15000,NULL,'Baru'),(6,9,68,1,15000,NULL,'Baru'),(7,9,69,2,15000,'sunaa','Baru'),(8,10,68,1,15000,NULL,'Baru'),(9,10,69,2,15000,'woww','Baru'),(10,11,68,1,15000,NULL,'Baru'),(12,12,68,2,15000,'test','Baru'),(13,13,68,1,15000,NULL,'Baru'),(14,14,3,1,18000,NULL,'Baru');
/*!40000 ALTER TABLE `detail_order_fnb` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `event_spaces`
--

DROP TABLE IF EXISTS `event_spaces`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `event_spaces` (
  `id_event_space` int(11) NOT NULL AUTO_INCREMENT,
  `nama_event_space` varchar(255) NOT NULL,
  `deskripsi_event_space` text DEFAULT NULL,
  `harga_paket` int(11) NOT NULL,
  `kapasitas` int(11) DEFAULT NULL,
  `status_ketersediaan` enum('Active','Inactive') NOT NULL DEFAULT 'Active',
  `gambar_ruangan` varchar(255) DEFAULT 'event_spaces.jpg',
  `fitur_ruangan` text DEFAULT NULL,
  PRIMARY KEY (`id_event_space`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `event_spaces`
--

LOCK TABLES `event_spaces` WRITE;
/*!40000 ALTER TABLE `event_spaces` DISABLE KEYS */;
INSERT INTO `event_spaces` VALUES (1,'Aula Serbaguna','Rencanakan acara Anda di aula indoor serbaguna yang dirancang untuk menghadirkan pengalaman terbaik bagi setiap peserta. Dengan desain interior yang modern, sistem tata suara yang jernih, serta suasana yang hangat dan eksklusif, aula ini menjadi pilihan ideal untuk menyelenggarakan seminar, workshop, maupun gathering yang berkesan.',1500000,50,'Active','aula.jpeg','Listrik \r\nWifi\r\nTempat Duduk\r\nMeja\r\nHalaman Luas'),(2,'Sewa Seluruh Open Space','Sewa seluruh area open space di lantai 1 untuk acara private. Termasuk semua meja dan kursi.',2500000,30,'Active','open_space_1-2.jpg','Desain fleksibel\r\nRuang luas \r\nCocok untuk pameran & workshop\r\nDekorasi bisa disesuaikan\r\nKursi & meja lengkap\r\nFull AC'),(3,'Sewa Full Venue Dago','Sewa seluruh fasilitas Dago Creative Hub untuk acara eksklusif Anda (termasuk open space, meeting room, dan aula).',5000000,100,'Inactive','full.jpg','Privasi penuh\r\nAkses ke semua fasilitas\r\nCocok untuk acara besar'),(6,'Sewa Space Lesehan','Sewa space lesehan dengan dudukan bantal dan meja',1000000,15,'Active','WhatsApp_Image_2025-10-01_at_16.53.43_14ea2543.jpg','Internet\r\nRefill Water\r\nNo Smoking\r\nRuangan Full AC\r\nMeja lesehan & bantal duduk\r\nAkses Wi-Fi\r\nColokan listrik'),(7,'aulaa','sss',10000,10,'Active','WhatsApp_Image_2025-11-09_at_22.46.17.jpeg','free wifi'),(8,'Lesehan ','Testimonial ',200000,20,'Active','Screenshot_2025-08-16-18-39-44-740_com.robtopx.geometryjumplite.jpg','Ac, wifi, tempat duduk\r\n');
/*!40000 ALTER TABLE `event_spaces` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `katalog_acara`
--

DROP TABLE IF EXISTS `katalog_acara`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `katalog_acara` (
  `id_acara` int(11) NOT NULL AUTO_INCREMENT,
  `judul_acara` varchar(255) NOT NULL,
  `tanggal_acara` date NOT NULL,
  `waktu_mulai` time NOT NULL,
  `waktu_selesai` time NOT NULL,
  `lokasi` varchar(255) DEFAULT NULL,
  `harga` varchar(100) DEFAULT 'Gratis',
  `deskripsi` text DEFAULT NULL,
  `tags` text DEFAULT NULL COMMENT 'Simpan sebagai comma-separated, cth: Teknologi,Bisnis',
  `gambar_url` varchar(255) DEFAULT 'default_event.jpg',
  `status_acara` enum('aktif','inaktif') NOT NULL DEFAULT 'aktif',
  PRIMARY KEY (`id_acara`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `katalog_acara`
--

LOCK TABLES `katalog_acara` WRITE;
/*!40000 ALTER TABLE `katalog_acara` DISABLE KEYS */;
INSERT INTO `katalog_acara` VALUES (1,'test','2025-11-10','08:00:00','17:00:00','aula','Gratis','test','Teknologi','a6049cc5-9385-4daa-9b97-73e199419b45_FTK.jpg','inaktif'),(3,'test','2025-11-13','08:00:00','17:00:00','aula','Gratis','test','Teknologi','608f67b7-f6c9-4f15-89e1-117d01545b89_FTK.jpg','inaktif');
/*!40000 ALTER TABLE `katalog_acara` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `kategori_produk`
--

DROP TABLE IF EXISTS `kategori_produk`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `kategori_produk` (
  `id_kategori` int(11) NOT NULL AUTO_INCREMENT,
  `id_tenant` int(11) NOT NULL,
  `nama_kategori` varchar(100) NOT NULL,
  `id_coa` int(11) DEFAULT NULL COMMENT 'Foreign Key ke chart_of_accounts',
  PRIMARY KEY (`id_kategori`),
  KEY `id_tenant` (`id_tenant`),
  KEY `fk_kategori_produk_coa` (`id_coa`),
  CONSTRAINT `fk_kategori_produk_coa` FOREIGN KEY (`id_coa`) REFERENCES `chart_of_accounts` (`id_coa`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `kategori_produk_ibfk_1` FOREIGN KEY (`id_tenant`) REFERENCES `tenants` (`id_tenant`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `kategori_produk`
--

LOCK TABLES `kategori_produk` WRITE;
/*!40000 ALTER TABLE `kategori_produk` DISABLE KEYS */;
INSERT INTO `kategori_produk` VALUES (3,3,'Espresso Based',NULL),(4,3,'Brewed Coffee',NULL),(5,4,'Makanan',NULL),(6,4,'Minuman',NULL),(7,4,'Ala Carte',NULL),(8,3,'Milk Based',NULL),(11,3,'Milkshake',NULL),(13,3,'Tea & Infusions',NULL),(14,3,'Mocktails & Juice',NULL),(15,3,'Snack',NULL),(16,3,'Sweet',NULL),(17,3,'Sandwich',NULL),(18,3,'Sides',NULL),(20,8,'Test',NULL),(23,8,'test_tenant3_kategori',NULL),(24,8,'test_category_tenantsss',NULL);
/*!40000 ALTER TABLE `kategori_produk` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `kategori_ruangan`
--

DROP TABLE IF EXISTS `kategori_ruangan`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `kategori_ruangan` (
  `id_kategori_ruangan` int(11) NOT NULL AUTO_INCREMENT,
  `nama_kategori` varchar(100) NOT NULL,
  `id_coa` int(11) DEFAULT NULL COMMENT 'Foreign Key ke chart_of_accounts',
  `deskripsi` text DEFAULT NULL,
  `gambar_kategori_ruangan` varchar(255) DEFAULT 'kategori.jpg',
  `status` enum('Active','Inactive') NOT NULL DEFAULT 'Active',
  PRIMARY KEY (`id_kategori_ruangan`),
  KEY `fk_kategori_ruangan_coa` (`id_coa`),
  CONSTRAINT `fk_kategori_ruangan_coa` FOREIGN KEY (`id_coa`) REFERENCES `chart_of_accounts` (`id_coa`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `kategori_ruangan`
--

LOCK TABLES `kategori_ruangan` WRITE;
/*!40000 ALTER TABLE `kategori_ruangan` DISABLE KEYS */;
INSERT INTO `kategori_ruangan` VALUES (1,'Space Monitor',NULL,'Minggu dan Libur Nasional tetap buka (khusus reservasi).\r\nArea space monitor yang nyaman dengan fasilitas lengkap dan monitor pribadi untuk mendukung efisiensi kerja.','space-monitor.jpeg','Active'),(3,'Open Space',NULL,'Minggu dan Libur Nasional tetap buka (khusus reservasi).\r\nArea open space yang nyaman dengan fasilitas lengkap untuk menunjang fokus dan produktivitas kerja.\r\n','open-space.jpeg','Active'),(4,'Room Meeting Besar',NULL,'Minggu dan Libur Nasional tetap buka (khusus reservasi).\r\nRuang meeting nyaman untuk 8 orang, dengan fasilitas lengkap yang mendukung produktivitas.\r\n','ruang-meeting.jpeg','Active'),(6,'Room Meeting Kecil',NULL,'Minggu dan Libur Nasional tetap buka (khusus reservasi).\r\nRuang meeting nyaman untuk 4-5 orang, dengan fasilitas lengkap yang mendukung produktivitas. ','ruang-meeting.jpeg','Active');
/*!40000 ALTER TABLE `kategori_ruangan` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `memberships`
--

DROP TABLE IF EXISTS `memberships`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `memberships` (
  `id_memberships` int(11) NOT NULL AUTO_INCREMENT,
  `id_user` int(11) NOT NULL,
  `id_paket_membership` int(11) NOT NULL,
  `id_transaksi` bigint(20) NOT NULL COMMENT 'Transaksi pembelian paket',
  `tanggal_mulai` date NOT NULL,
  `tanggal_berakhir` date NOT NULL,
  `total_credit` int(11) NOT NULL,
  `sisa_credit` int(11) NOT NULL,
  `no_hp` int(11) DEFAULT NULL,
  `status_memberships` enum('Active','Inactive') NOT NULL,
  PRIMARY KEY (`id_memberships`),
  KEY `id_user` (`id_user`),
  KEY `id_paket_membership` (`id_paket_membership`),
  KEY `id_transaksi` (`id_transaksi`),
  CONSTRAINT `memberships_ibfk_1` FOREIGN KEY (`id_user`) REFERENCES `users` (`id_user`) ON DELETE CASCADE,
  CONSTRAINT `memberships_ibfk_2` FOREIGN KEY (`id_paket_membership`) REFERENCES `paket_membership` (`id_paket_membership`),
  CONSTRAINT `memberships_ibfk_3` FOREIGN KEY (`id_transaksi`) REFERENCES `transaksi` (`id_transaksi`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `memberships`
--

LOCK TABLES `memberships` WRITE;
/*!40000 ALTER TABLE `memberships` DISABLE KEYS */;
INSERT INTO `memberships` VALUES (1,107,17,4,'2025-11-17','2025-12-17',33,33,NULL,'Active');
/*!40000 ALTER TABLE `memberships` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `paket_harga_ruangan`
--

DROP TABLE IF EXISTS `paket_harga_ruangan`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `paket_harga_ruangan` (
  `id_paket` bigint(20) NOT NULL AUTO_INCREMENT,
  `id_ruangan` int(11) NOT NULL,
  `durasi_jam` int(11) NOT NULL,
  `harga_paket` int(11) NOT NULL,
  PRIMARY KEY (`id_paket`),
  KEY `id_ruangan` (`id_ruangan`),
  CONSTRAINT `paket_harga_ruangan_ibfk_1` FOREIGN KEY (`id_ruangan`) REFERENCES `ruangan` (`id_ruangan`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=102 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `paket_harga_ruangan`
--

LOCK TABLES `paket_harga_ruangan` WRITE;
/*!40000 ALTER TABLE `paket_harga_ruangan` DISABLE KEYS */;
INSERT INTO `paket_harga_ruangan` VALUES (1,4,2,26000),(2,4,3,40000),(3,4,6,60000),(4,4,8,80000),(5,2,2,100000),(11,13,2,20000),(12,13,3,30000),(13,13,6,50000),(14,13,8,70000),(15,19,2,20000),(16,19,3,30000),(17,19,6,50000),(18,19,8,70000),(19,21,2,20000),(20,21,3,30000),(21,21,6,50000),(22,21,8,70000),(23,20,2,20000),(25,22,2,20000),(26,22,3,30000),(27,22,6,50000),(28,20,3,30000),(29,22,8,70000),(30,23,2,20000),(32,23,6,50000),(33,23,8,70000),(34,20,6,50000),(35,20,8,70000),(36,24,2,20000),(37,24,3,30000),(38,24,6,50000),(39,14,2,20000),(40,24,8,70000),(41,14,3,30000),(42,14,6,50000),(43,14,8,70000),(44,15,2,20000),(45,15,3,30000),(46,15,6,50000),(47,15,8,70000),(48,25,2,20000),(49,25,3,30000),(50,16,2,20000),(51,25,6,50000),(52,16,3,30000),(53,25,8,70000),(54,16,6,50000),(55,16,8,70000),(56,17,2,20000),(57,17,3,30000),(58,17,6,50000),(59,17,8,70000),(60,18,2,20000),(61,18,3,30000),(62,18,6,50000),(63,18,8,70000),(64,26,2,75000),(65,26,4,150000),(66,26,8,250000),(67,27,2,75000),(68,27,4,150000),(69,27,8,250000),(70,1,2,20000),(71,1,3,30000),(72,1,6,50000),(73,1,8,70000),(74,23,3,30000),(75,5,2,26000),(76,5,3,40000),(77,5,6,60000),(78,5,8,80000),(79,6,2,26000),(80,6,3,40000),(81,6,6,60000),(82,6,8,80000),(83,7,2,26000),(84,7,3,40000),(85,7,6,60000),(86,7,8,80000),(87,8,2,26000),(88,8,3,40000),(89,8,6,60000),(90,8,8,80000),(95,2,4,200000),(96,2,8,300000);
/*!40000 ALTER TABLE `paket_harga_ruangan` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `paket_membership`
--

DROP TABLE IF EXISTS `paket_membership`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `paket_membership` (
  `id_paket_membership` int(11) NOT NULL AUTO_INCREMENT,
  `id_kategori_ruangan` int(11) NOT NULL,
  `nama_paket` varchar(255) NOT NULL,
  `harga` int(11) NOT NULL,
  `durasi` int(11) NOT NULL COMMENT 'Durasi dalam hari',
  `kuota` int(11) NOT NULL COMMENT 'Jumlah kredit yang didapat',
  `deskripsi_benefit` text DEFAULT NULL,
  `fitur_membership` text DEFAULT NULL,
  `status_paket` enum('Active','Inactive') NOT NULL DEFAULT 'Active',
  PRIMARY KEY (`id_paket_membership`),
  KEY `id_kategori_ruangan` (`id_kategori_ruangan`),
  CONSTRAINT `paket_membership_ibfk_1` FOREIGN KEY (`id_kategori_ruangan`) REFERENCES `kategori_ruangan` (`id_kategori_ruangan`)
) ENGINE=InnoDB AUTO_INCREMENT=56 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `paket_membership`
--

LOCK TABLES `paket_membership` WRITE;
/*!40000 ALTER TABLE `paket_membership` DISABLE KEYS */;
INSERT INTO `paket_membership` VALUES (1,3,'Open Space Basic (1 bulan)',250000,30,28,'-','🌐 Wi-Fi Member\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ AC','Active'),(2,3,'Open Space Basic (3 bulan)',700000,90,80,'-','🌐 Wi-Fi Member\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ AC','Active'),(3,3,'Open Space Basic (6 bulan)',1350000,240,165,'-','🌐 Wi-Fi Member\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ AC','Active'),(8,3,'Open Space Basic (12 bulan)',2400000,360,350,'-','🌐 Wi-Fi Member\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ AC','Active'),(9,3,'Open Space Standard (1 bulan)',400000,30,45,'-','🌐 Wi-Fi Member\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ AC','Active'),(10,3,'Open Space Standard (3 bulan)',1140000,90,140,'-','🌐 Wi-Fi Member\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ AC','Active'),(11,3,'Open Space Standard (6 bulan)',2280000,180,310,'-','🌐 Wi-Fi Member\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ AC','Active'),(12,3,'Open Space Standard (12 Bulan)',3840000,360,600,'-','🌐 Wi-Fi Member\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ AC','Active'),(13,3,'Open Space Premium (1 Bulan)',550000,30,70,'-','🌐 Wi-Fi Member\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ AC','Active'),(14,3,'Open Space Premium (3 Bulan)',1570000,90,200,'-','🌐 Wi-Fi Member\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ AC','Active'),(15,3,'Open Space Premium (6 Bulan)',3150000,180,430,'-','🌐 Wi-Fi Member\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ AC','Active'),(16,3,'Open Space Premium (12 Bulan)',5280000,360,850,'-','🌐 Wi-Fi Member\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ AC','Active'),(17,1,'Space Monitor Basic (1 Bulan)',350000,30,33,'-','🌐 Wi-Fi Member\n🖥️ Monitor Eksternal 24-inch\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ Ruangan Full AC','Active'),(18,1,'Space Monitor Basic (3 Bulan)',975000,90,95,'-','🌐 Wi-Fi Member\n🖥️ Monitor Eksternal 24-inch\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ Ruangan Full AC','Active'),(19,1,'Space Monitor Basic (6 Bulan)',1850000,180,200,'-','🌐 Wi-Fi Member\n🖥️ Monitor Eksternal 24-inch\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ Ruangan Full AC','Active'),(20,1,'Space Monitor Basic (12 Bulan)',3360000,360,420,'-','🌐 Wi-Fi Member\n🖥️ Monitor Eksternal 24-inch\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ Ruangan Full AC','Active'),(21,1,'Space Monitor Standard (1 Bulan)',550000,30,53,'-','🌐 Wi-Fi Member\n🖥️ Monitor Eksternal 24-inch\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ Ruangan Full AC','Active'),(22,1,'Space Monitor Standard (3 Bulan)',1565000,90,155,'-','🌐 Wi-Fi Member\n🖥️ Monitor Eksternal 24-inch\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ Ruangan Full AC','Active'),(23,1,'Space Monitor Standard (6 Bulan)',2970000,180,330,'-','🌐 Wi-Fi Member\n🖥️ Monitor Eksternal 24-inch\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ Ruangan Full AC','Active'),(24,1,'Space Monitor Standard (12 Bulan)',5280000,360,660,'-','🌐 Wi-Fi Member\n🖥️ Monitor Eksternal 24-inch\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ Ruangan Full AC','Active'),(25,1,'Space Monitor Premium (1 Bulan)',750000,30,75,'-','🌐 Wi-Fi Member\n🖥️ Monitor Eksternal 24-inch\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ Ruangan Full AC','Active'),(26,1,'Space Monitor Premium (3 Bulan)',2140000,90,210,'-','🌐 Wi-Fi Member\n🖥️ Monitor Eksternal 24-inch\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ Ruangan Full AC','Active'),(27,1,'Space Monitor Premium (6 Bulan)',4050000,180,465,'-','🌐 Wi-Fi Member\n🖥️ Monitor Eksternal 24-inch\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ Ruangan Full AC','Active'),(28,1,'Space Monitor Premium (12 Bulan)',7200000,360,900,'-','🌐 Wi-Fi Member\n🖥️ Monitor Eksternal 24-inch\n🔌Kabel HDMI\n🪑Meja & Kursi\n⚡Akses Listrik Pribadi\n❄️ Ruangan Full AC','Active'),(29,6,'Room Meeting Kecil Basic (1 Bulan)',500000,30,40,'-','🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(30,6,'Room Meeting Kecil Basic (3 Bulan)',1395000,90,120,'-','🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(31,6,'Room Meeting Kecil Basic (6 Bulan)',2640000,180,260,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(32,6,'Room Meeting Kecil Basic (12 Bulan )',4800000,360,560,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(33,6,'Room Meeting Kecil Standard (1 Bulan)',750000,30,60,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(34,6,'Room Meeting Kecil Standard (3 Bulan)',2140000,90,180,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(35,6,'Room Meeting Kecil Standard (6 Bulan)',4050000,180,390,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(36,6,'Room Meeting Kecil Standard (12 Bulan)',7200000,360,840,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(37,4,'Meeting Room Kecil Premium (1 Bulan)',1000000,30,90,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(38,6,'Room Meeting Kecil Premium (3 Bulan)',2850000,90,270,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(39,6,'Room Meeting Kecil Premium (6 Bulan)',5400000,180,270,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(40,6,'Room Meeting Kecil Premium (12 Bulan)',9600000,360,1200,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(41,4,'Room Meeting Besar Basic (1 Bulan)',700000,30,45,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(42,4,'Room Meeting Besar Basic (3 Bulan)',1955000,90,148,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(43,4,'Room Meeting Besar Basic (6 Bulan)',3695000,180,310,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(44,4,'Room Meeting Besar Basic (12 Bulan)',6720000,360,675,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(45,4,'Room Meeting Besar Standard (1 Bulan)',1000000,30,70,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(46,4,'Room Meeting Besar Standard (3 Bulan)',2850000,90,210,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(47,4,'Room Meeting Besar Standard (6 Bulan)',5400000,180,420,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(48,4,'Room Meeting Besar Standard (12 Bulan)',9600000,360,840,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(49,4,'Room Meeting Besar Premium (1 Bulan)',1300000,30,100,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(50,4,'Room Meeting Besar Premium (3 Bulan)',3705000,90,300,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(51,4,'Room Meeting Besar Premium (6 Bulan)',7020000,180,600,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(52,4,'Room Meeting Besar Premium (12 Bulan)',13440000,360,1500,NULL,'🖥️ Smart TV dengan port HDMI\n❄️ Ruangan Pribadi Full AC\n🌐 Wi-Fi Member\n🔌 Akses Colokan Listrik di Area Meja\n🪑 Meja & Kursi \n⚡ Akses Listrik Pribadi ','Active'),(54,6,'Basic_test',500000,30,100,'test','test','Active');
/*!40000 ALTER TABLE `paket_membership` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `paket_virtual_office`
--

DROP TABLE IF EXISTS `paket_virtual_office`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `paket_virtual_office` (
  `id_paket_vo` int(11) NOT NULL AUTO_INCREMENT,
  `nama_paket` varchar(255) NOT NULL,
  `harga` int(11) NOT NULL,
  `durasi` int(11) NOT NULL COMMENT 'Durasi dalam hari',
  `benefit_jam_meeting_room_per_bulan` int(11) DEFAULT 0,
  `benefit_jam_working_space_per_bulan` int(11) DEFAULT 0,
  `deskripsi_layanan` text DEFAULT NULL,
  `status` enum('Active','Inactive') NOT NULL DEFAULT 'Active',
  PRIMARY KEY (`id_paket_vo`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `paket_virtual_office`
--

LOCK TABLES `paket_virtual_office` WRITE;
/*!40000 ALTER TABLE `paket_virtual_office` DISABLE KEYS */;
INSERT INTO `paket_virtual_office` VALUES (1,'Paket 6 Bulan',1750000,180,4,8,NULL,'Active'),(2,'Paket 12 Bulan',2950000,365,8,12,NULL,'Active'),(4,'paket 24 bulan',1750000,700,10,20,'tes','Active'),(6,'Paket 7 bulan',200000,180,3,2,'Testimonial ','Inactive');
/*!40000 ALTER TABLE `paket_virtual_office` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `pembayaran_pajak`
--

DROP TABLE IF EXISTS `pembayaran_pajak`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `pembayaran_pajak` (
  `id_pembayaran` int(11) NOT NULL AUTO_INCREMENT,
  `periode_mulai` date NOT NULL,
  `periode_selesai` date NOT NULL,
  `jumlah_dibayar` decimal(15,2) NOT NULL,
  `tanggal_bayar` date NOT NULL,
  `timestamp_catat` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id_pembayaran`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `pembayaran_pajak`
--

LOCK TABLES `pembayaran_pajak` WRITE;
/*!40000 ALTER TABLE `pembayaran_pajak` DISABLE KEYS */;
/*!40000 ALTER TABLE `pembayaran_pajak` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `pengeluaran_operasional`
--

DROP TABLE IF EXISTS `pengeluaran_operasional`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `pengeluaran_operasional` (
  `id_pengeluaran` bigint(20) NOT NULL AUTO_INCREMENT,
  `tanggal_pengeluaran` date NOT NULL,
  `kategori` varchar(50) NOT NULL,
  `deskripsi` text NOT NULL,
  `jumlah` int(11) NOT NULL,
  `dicatat_oleh` int(11) DEFAULT NULL COMMENT 'FK ke tabel users (admin)',
  `timestamp_catat` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id_pengeluaran`),
  KEY `dicatat_oleh` (`dicatat_oleh`),
  CONSTRAINT `pengeluaran_operasional_ibfk_1` FOREIGN KEY (`dicatat_oleh`) REFERENCES `users` (`id_user`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `pengeluaran_operasional`
--

LOCK TABLES `pengeluaran_operasional` WRITE;
/*!40000 ALTER TABLE `pengeluaran_operasional` DISABLE KEYS */;
/*!40000 ALTER TABLE `pengeluaran_operasional` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `penggunaan_benefit_vo`
--

DROP TABLE IF EXISTS `penggunaan_benefit_vo`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `penggunaan_benefit_vo` (
  `id_penggunaan` bigint(20) NOT NULL AUTO_INCREMENT,
  `id_client_vo` int(11) NOT NULL,
  `id_booking` bigint(20) NOT NULL,
  `jenis_benefit` enum('meeting_room','working_space') NOT NULL,
  `durasi_terpakai_menit` int(11) NOT NULL COMMENT 'Durasi benefit yang digunakan dalam menit',
  `tanggal_penggunaan` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id_penggunaan`),
  KEY `id_client_vo` (`id_client_vo`),
  KEY `id_booking` (`id_booking`),
  CONSTRAINT `penggunaan_benefit_vo_ibfk_1` FOREIGN KEY (`id_client_vo`) REFERENCES `client_virtual_office` (`id_client_vo`) ON DELETE CASCADE,
  CONSTRAINT `penggunaan_benefit_vo_ibfk_2` FOREIGN KEY (`id_booking`) REFERENCES `booking_ruangan` (`id_booking`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `penggunaan_benefit_vo`
--

LOCK TABLES `penggunaan_benefit_vo` WRITE;
/*!40000 ALTER TABLE `penggunaan_benefit_vo` DISABLE KEYS */;
/*!40000 ALTER TABLE `penggunaan_benefit_vo` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `produk_fnb`
--

DROP TABLE IF EXISTS `produk_fnb`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `produk_fnb` (
  `id_produk` int(11) NOT NULL AUTO_INCREMENT,
  `id_kategori` int(11) NOT NULL,
  `nama_produk` varchar(255) NOT NULL,
  `deskripsi_produk` text DEFAULT NULL,
  `harga` int(11) NOT NULL,
  `status_ketersediaan` enum('Active','Inactive') NOT NULL DEFAULT 'Active',
  `status_visibilitas` enum('Aktif','Nonaktif') NOT NULL DEFAULT 'Aktif',
  `foto_produk` varchar(255) NOT NULL DEFAULT 'kopi.jpg',
  PRIMARY KEY (`id_produk`),
  KEY `id_kategori` (`id_kategori`),
  CONSTRAINT `produk_fnb_ibfk_1` FOREIGN KEY (`id_kategori`) REFERENCES `kategori_produk` (`id_kategori`)
) ENGINE=InnoDB AUTO_INCREMENT=75 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `produk_fnb`
--

LOCK TABLES `produk_fnb` WRITE;
/*!40000 ALTER TABLE `produk_fnb` DISABLE KEYS */;
INSERT INTO `produk_fnb` VALUES (3,3,'Americano','Bold Espresso Mellowed with hot water for a smooth, rich sip',18000,'Active','Aktif','Biru__Putih_Minimalis_Promosi_Menu_Mie_Ayam_Kiriman_Instagram_5.png'),(4,4,'Chocolate','Warm, velvety cocoa comfort.',22000,'Inactive','Aktif','1.png'),(5,5,'Rice Bowls Chicken Blackpaper','Nasi putih, chicken pop, saus kental blackpepper, selada, dan taburan wijen sangrai',15000,'Inactive','Aktif','Rice Bowl Black Pepper.png'),(6,6,'Es Campur','Jelly, cincau, kolang-kaling, bijik, rumput laut, tape singkong, siraman gula merah & susu kental manis.',5000,'Inactive','Aktif','Es Campur.png'),(7,7,'Risol','Varian rasa: Makaroni, mayo, sosis, ayam, sayur (mix random)',13000,'Inactive','Aktif','Risol.png'),(8,5,'Mie Kuah','Mie kuah dengan poached egg (bisa request setengah matang), dan cabai iris',10000,'Inactive','Aktif','Mie_Kuah.png'),(9,5,'Mie Bangladesh (Mie Nyemek)','Mie goreng nyemek, dengan poached egg setengah matang, sayur ijo, pangsit',15000,'Inactive','Aktif','Mie_Bangladesh_Mie_Nyemek.png'),(10,5,'Rice Bowl Spicy Chicken','Nasi putih, dengan chicken pop, saus kental pedas manis, selada, dan taburan wijen sangrai',15000,'Inactive','Aktif','6.png'),(11,5,'Rice Bowl Sambal Matah','Nasi putih, chicken pop, sambal matah (irisan bawang merah & cabe rawit), serta selada',15000,'Inactive','Aktif','Rice_Bowl_Sambel_Matah.png'),(12,5,'Rice Bowl Cabe Garam','Nasi putih, chicken pop, bumbu cabe garam dengan sedikit minyak, daun pre, dan selada',15000,'Inactive','Aktif','Rice_Bowl_Cabe_Garam.png'),(13,7,'Mix Plater','Isi: Kentang goreng, sosis, nugget, tahu ikan\r\nPendamping: Saus sambal & mayo',20000,'Inactive','Aktif','Mix_Plater.png'),(14,5,'Omlete','Isi: Telur dadar dengan bombai & paprika\r\nPendamping: Saus sambal & mayo',20000,'Inactive','Aktif','Biru__Putih_Minimalis_Promosi_Menu_Mie_Ayam_Kiriman_Instagram.png'),(15,7,'Telur','(Extra Topping) Mata sapi/poached egg',5000,'Inactive','Aktif','Nakso_bakar_4.png'),(16,7,'Sosis','(Extra Topping)',5000,'Inactive','Aktif','Nakso_bakar_5.png'),(17,7,'Ayam Suir','(Extra Topping)',5000,'Inactive','Aktif','Brown_Sugar_Milk_Tea.png'),(18,6,'Air Mineral','',5000,'Inactive','Aktif','Biru__Putih_Minimalis_Promosi_Menu_Mie_Ayam_Kiriman_Instagram_2.png'),(20,7,'Es Krim Sandwich','Es krim potong (mix 3 rasa (cokelat, vanilla, stroberi)), roti tawar, topping choco chip, sprinkle warna-warni dan susu kental manis cokelat',13000,'Inactive','Aktif','Es_Krim_Sandwich.png'),(21,5,'Nasigor Ngejengit (All Level)','Level pedas: 0–6 🌶️\r\nNasi goreng cokelat (kecap), telur mata sapi (bisa request setengah matang), sayur ijo & kol, pangsit/kerupuk (tergantung persediaan)\r\n',15000,'Inactive','Aktif','14.png'),(22,5,'Miegor Ngejengit (All Level)','Level pedas: 0–6 🌶️\r\nMie kuning, telur mata sapi (bisa request setengah matang), sayur ijo & kol, pangsit',15000,'Inactive','Aktif','15.png'),(23,5,'Chicken Katsu Bumbu Kare','Nasi putih, ayam fillet berbalut tepung roti, kuah kare (berisi potongan kentang & wortel), dan selada',20000,'Inactive','Aktif','7.png'),(24,7,'Pisang Nugget Keju Cokelat','Isi 5 pcs pisang berbalut tepung roti, topping parutan cokelat dan keju, dan susu kental manis vanilla',10000,'Inactive','Aktif','Biru__Putih_Minimalis_Promosi_Menu_Mie_Ayam_Kiriman_Instagram_3.png'),(25,5,'Kentang Goreng','',15000,'Inactive','Aktif','Biru__Putih_Minimalis_Promosi_Menu_Mie_Ayam_Kiriman_Instagram_1.png'),(26,3,'Americano/Long Black','Espresso with water',18000,'Inactive','Aktif','AMERIKANO_3.png'),(27,3,'Cappuccino','Frothy espresso beverage',22000,'Inactive','Aktif','CAPPUCINO.png'),(28,3,'Moccachino','Chocolate creamy espresso',24000,'Inactive','Aktif','MOCCACCINO.png'),(29,3,'Cafe Latte','Creamy esspresso drink',22000,'Inactive','Aktif','AMERIKANO.png'),(30,3,'Homebro\'s Special','You can\'t find somewhere else',25000,'Inactive','Aktif','Brown_Sugar_Milk_Tea_1.png'),(31,3,'Black Honey','Americano with honey',22000,'Inactive','Aktif','blackhonyKELAdi.png'),(32,3,'Oat Latte','Oat milk latte',25000,'Inactive','Aktif','OAT_LATTE.png'),(33,3,'Spanish Latte','Sweet & creamy latte',25000,'Inactive','Aktif','SPAISH_LATTE.png'),(34,4,'Kopi Tubruk','Balinese black coffee',10000,'Inactive','Aktif','Nakso_bakar_6.png'),(35,4,'Tubruk Susu','Balinese black coffee with milk',15000,'Inactive','Aktif','TUBRUK_SUSU.png'),(36,8,'Le Mocca','Sweet & creamy chocolate drinks',22000,'Inactive','Aktif','Nakso_bakar_7.png'),(37,8,'Matcha Latte','Smooth caffeine shooter',22000,'Inactive','Aktif','MATCHA_LATTE.png'),(38,8,'Strawberry Mocca','Fresh, sweet & creamy drinks',24,'Inactive','Aktif','STOBERRY_MOCCA.png'),(39,8,'Strawberry Matcha','Fresh, sweet & creamy drinks',24000,'Inactive','Aktif','AMERIKANO_1.png'),(40,8,'Honey Oat Matcha','Tasty matcha with honey hint',25000,'Inactive','Aktif','HONEY_OAT_MATCHA.png'),(41,8,'Oat Matcha','Tasty chocolate drinks',25000,'Inactive','Aktif','OAT_MATCHA.png'),(42,11,'Chocolate','Sweet & creamy chocolate drinks',23000,'Inactive','Aktif','cho_LATTE.png'),(43,11,'Vanilla','Creamy vanilla milkshake',23000,'Inactive','Aktif','vanila_LATTE.png'),(44,11,'Straw Hat Berry','Fresh & creamy',23000,'Inactive','Aktif','stoby.png'),(45,11,'Coffee Frappe','Your sweet caffeine booster',25000,'Inactive','Aktif','stoby_1.png'),(46,13,'Black Tea','',10000,'Inactive','Aktif','black_tea.png'),(47,13,'Ginger Tea','',12000,'Inactive','Aktif','ginger.png'),(48,13,'Lemongrass','',12000,'Inactive','Aktif','leon_grass.png'),(49,13,'Lychee Tea','',12000,'Inactive','Aktif','lyce.png'),(50,13,'Brown Sugar Milk Tea','',18000,'Inactive','Aktif','CAPPUCINO_1.png'),(51,14,'Lychee Squash','',15000,'Inactive','Aktif','Biru__Putih_Minimalis_Promosi_Menu_Mie_Ayam_Kiriman_Instagram_6.png'),(52,14,'Melon Squash','',15000,'Inactive','Aktif','Nakso_bakar_2.png'),(53,14,'Orange Squash','',15000,'Inactive','Aktif','Nakso_bakar_1.png'),(54,14,'Lime Squash','',15000,'Inactive','Aktif','Nakso_bakar.png'),(55,14,'Juice by Fruit in Season','',18000,'Inactive','Aktif','LE_MOCCA_12.png'),(56,15,'Kentang Sambal Embe','',18000,'Inactive','Aktif','LE_MOCCA_11.png'),(57,15,'Bakwan Keladi','',10000,'Inactive','Aktif','BAKWAN_KELAdi.png'),(58,15,'Chicken Wings','',18000,'Inactive','Aktif','LE_MOCCA_1.png'),(59,16,'Pisang Goreng','',10000,'Inactive','Aktif','LE_MOCCA_9.png'),(60,16,'Pisang Gulung','',10000,'Inactive','Aktif','LE_MOCCA_8.png'),(61,16,'Pancake','Chocolate / Strawberry',15000,'Inactive','Aktif','AMERIKANO_2.png'),(62,16,'Roti Bakar','Chocolate/Strawberry',15000,'Inactive','Aktif','LE_MOCCA.png'),(63,17,'Chicken Sandwich','Chicken lettuce tomato on toasted bread',22000,'Inactive','Aktif','LE_MOCCA_7.png'),(64,17,'Egg & Cheese','Flufy eggs and melty cheese between warm slices',20000,'Inactive','Aktif','LE_MOCCA_6.png'),(65,17,'Chicken Kebab','Lettuce, crispy chicken, yummy souce, wrapped in tortilla',15000,'Inactive','Aktif','LE_MOCCA_5.png'),(66,18,'Bakso Bakar','',12000,'Inactive','Aktif','LE_MOCCA_4.png'),(67,18,'Sosis Bakar','',12000,'Active','Aktif','LE_MOCCA_3.png'),(68,18,'Dimsum','',15000,'Active','Aktif','LE_MOCCA_2.png'),(69,5,'Nasgor Suna Cekuh','',15000,'Active','Aktif','Biru__Putih_Minimalis_Promosi_Menu_Mie_Ayam_Kiriman_Instagram_4.png'),(74,23,'test_tenant3_produk','test_tenant3_produk_deskripsi',10000,'Inactive','Aktif','unnamed.jpg');
/*!40000 ALTER TABLE `produk_fnb` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `promo`
--

DROP TABLE IF EXISTS `promo`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `promo` (
  `id_promo` int(11) NOT NULL AUTO_INCREMENT,
  `kode_promo` varchar(50) NOT NULL,
  `deskripsi_promo` text DEFAULT NULL,
  `nilai_diskon` decimal(10,2) NOT NULL,
  `tanggal_mulai` date NOT NULL,
  `tanggal_selesai` date NOT NULL,
  `waktu_mulai` time DEFAULT NULL,
  `waktu_selesai` time DEFAULT NULL,
  `status_aktif` enum('aktif','inaktif') NOT NULL DEFAULT 'inaktif',
  `syarat` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`syarat`)),
  PRIMARY KEY (`id_promo`),
  UNIQUE KEY `kode_promo` (`kode_promo`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `promo`
--

LOCK TABLES `promo` WRITE;
/*!40000 ALTER TABLE `promo` DISABLE KEYS */;
INSERT INTO `promo` VALUES (1,'SARAPANHEMAT','Diskon Rp 5.000 untuk semua menu F&B. Hanya berlaku di pagi hari.',5000.00,'2025-10-01','2025-10-31','08:00:00','10:00:00','inaktif',NULL),(2,'HAPPYHOURSORE_EDITED','Diskon 20% untuk semua minuman kopi. Nikmati sore harimu!',20.00,'2025-10-01','2025-12-31','15:00:00','18:00:00','inaktif',NULL),(3,'MEETINGPAKET','Diskon 15% untuk booking Ruang Meeting di atas 3 jam.',15000.00,'2025-10-01','2025-10-31',NULL,NULL,'inaktif','{\"min_durasi_jam\": 3}'),(4,'SEPTEMBERCERIA','Promo bulan lalu yang sudah tidak aktif.',10.00,'2025-09-01','2025-09-30',NULL,NULL,'inaktif',NULL),(5,'AKHIRTAHUN2025','Promo yang akan datang untuk menyambut liburan akhir tahun.',25.00,'2025-12-20','2025-12-31','08:00:00','22:00:00','aktif',NULL),(6,'OKTOBER10.10DEALS','Promo pesan makanan atau tempat di Dago',50000.00,'2025-10-01','2025-10-31','10:00:00','22:00:00','inaktif',NULL),(8,'NOVEMBERASIQ_TEST','Testimonial ',7000.00,'2025-11-11','2025-11-30','10:00:00','15:00:00','aktif',NULL);
/*!40000 ALTER TABLE `promo` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `rekap_bagi_hasil`
--

DROP TABLE IF EXISTS `rekap_bagi_hasil`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `rekap_bagi_hasil` (
  `id_rekap_bagi_hasil` int(11) NOT NULL AUTO_INCREMENT,
  `id_tenant` int(11) NOT NULL,
  `periode_bulan` int(11) NOT NULL,
  `periode_tahun` int(11) NOT NULL,
  `utang_awal` decimal(10,2) NOT NULL DEFAULT 0.00,
  `sales_p1` decimal(10,2) DEFAULT NULL COMMENT 'Manual override untuk sales P1',
  `sales_p2` decimal(10,2) DEFAULT NULL COMMENT 'Manual override untuk sales P2',
  `status_pembayaran_t1` tinyint(1) NOT NULL DEFAULT 0,
  `status_pembayaran_t2` tinyint(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id_rekap_bagi_hasil`),
  UNIQUE KEY `idx_tenant_periode` (`id_tenant`,`periode_bulan`,`periode_tahun`),
  CONSTRAINT `fk_rekap_tenant` FOREIGN KEY (`id_tenant`) REFERENCES `tenants` (`id_tenant`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `rekap_bagi_hasil`
--

LOCK TABLES `rekap_bagi_hasil` WRITE;
/*!40000 ALTER TABLE `rekap_bagi_hasil` DISABLE KEYS */;
/*!40000 ALTER TABLE `rekap_bagi_hasil` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `ruangan`
--

DROP TABLE IF EXISTS `ruangan`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ruangan` (
  `id_ruangan` int(11) NOT NULL AUTO_INCREMENT,
  `id_kategori_ruangan` int(11) NOT NULL,
  `nama_ruangan` varchar(255) NOT NULL,
  `harga_per_jam` int(11) NOT NULL,
  `deskripsi_ruangan` text DEFAULT NULL,
  `kapasitas` int(11) DEFAULT NULL,
  `status_ketersediaan` enum('Active','Inactive') NOT NULL DEFAULT 'Active',
  `gambar_ruangan` varchar(255) NOT NULL DEFAULT 'ruangan.jpg',
  `fitur_ruangan` text NOT NULL,
  PRIMARY KEY (`id_ruangan`),
  KEY `id_kategori_ruangan` (`id_kategori_ruangan`),
  CONSTRAINT `ruangan_ibfk_1` FOREIGN KEY (`id_kategori_ruangan`) REFERENCES `kategori_ruangan` (`id_kategori_ruangan`)
) ENGINE=InnoDB AUTO_INCREMENT=33 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ruangan`
--

LOCK TABLES `ruangan` WRITE;
/*!40000 ALTER TABLE `ruangan` DISABLE KEYS */;
INSERT INTO `ruangan` VALUES (1,3,'Open Space 01',20000,'Temukan fokus dan inspirasi Anda di Open Space 01.\r\nSebuah ruang kerja bersama yang dirancang untuk kenyamanan dan produktivitas maksimal. ',1,'Active','Openspace.jpg','Durasi 2-8 Jam\r\nMeja & Kursi \r\nAkses Listrik di Setiap Meja\r\nRuangan Full AC\r\nKoneksi Wi-Fi Cepat'),(2,4,'Ruang Meeting Besar 01',75000,'Ciptakan sesi diskusi yang produktif dan lancar di Ruang Meeting 01. Dirancang secara profesional untuk menampung hingga 8 orang, ruangan ini menyediakan suasana yang kondusif untuk diskusi penting atau presentasi yang memukau.',8,'Active','ruang_meeting_1.jpg','Durasi 2-8 Jam\r\nSmart TV dengan port HDMI\r\nPrivate room\r\nRuangan Full AC \r\nKoneksi Wi-Fi Cepat & Stabil\r\nAkses Colokan Listrik di Area Meja'),(4,1,'Space Monitor 01',26000,'Tingkatkan produktivitas Anda ke level berikutnya dengan Space Monitor. Dirancang khusus bagi para profesional, desainer, dan developer yang membutuhkan ruang layar lebih luas, setiap workstation dilengkapi dengan monitor eksternal 24-inch yang jernih dan tajam.',1,'Active','space-monitor.jpeg','Durasi 2-8 Jam\r\nMonitor Eksternal 24-inch\r\nKabel HDMI \r\nMeja & Kursi\r\nAkses Listrik Pribadi\r\nKoneksi Wi-Fi Cepat\r\nRuangan Full AC'),(5,1,'Space Monitor 02',26000,'Tingkatkan produktivitas Anda ke level berikutnya dengan Space Monitor. Dirancang khusus bagi para profesional, desainer, dan developer yang membutuhkan ruang layar lebih luas, setiap workstation dilengkapi dengan monitor eksternal 24-inch yang jernih dan tajam.',1,'Active','space-monitor.jpeg','Durasi 2-8 Jam\r\nMonitor Eksternal 24-inch\r\nKabel HDMI \r\nMeja & Kursi\r\nAkses Listrik Pribadi\r\nKoneksi Wi-Fi Cepat\r\nRuangan Full AC'),(6,1,'Space Monitor 03',26000,'Tingkatkan produktivitas Anda ke level berikutnya dengan Space Monitor. Dirancang khusus bagi para profesional, desainer, dan developer yang membutuhkan ruang layar lebih luas, setiap workstation dilengkapi dengan monitor eksternal 24-inch yang jernih dan tajam.',1,'Active','space-monitor.jpeg','Durasi 2-8 Jam\r\nMonitor Eksternal 24-inch\r\nKabel HDMI \r\nMeja & Kursi\r\nAkses Listrik Pribadi\r\nKoneksi Wi-Fi Cepat\r\nRuangan Full AC'),(7,1,'Space Monitor 04',26000,'Tingkatkan produktivitas Anda ke level berikutnya dengan Space Monitor. Dirancang khusus bagi para profesional, desainer, dan developer yang membutuhkan ruang layar lebih luas, setiap workstation dilengkapi dengan monitor eksternal 24-inch yang jernih dan tajam.',1,'Active','space-monitor.jpeg','Durasi 2-8 Jam\r\nMonitor Eksternal 24-inch\r\nKabel HDMI \r\nMeja & Kursi\r\nAkses Listrik Pribadi\r\nKoneksi Wi-Fi Cepat\r\nRuangan Full AC'),(8,1,'Space Monitor 05',26000,'Tingkatkan produktivitas Anda ke level berikutnya dengan Space Monitor. Dirancang khusus bagi para profesional, desainer, dan developer yang membutuhkan ruang layar lebih luas, setiap workstation dilengkapi dengan monitor eksternal 24-inch yang jernih dan tajam.',1,'Active','space-monitor.jpeg','Durasi 2-8 Jam\r\nMonitor Eksternal 24-inch\r\nKabel HDMI \r\nMeja & Kursi\r\nAkses Listrik Pribadi\r\nKoneksi Wi-Fi Cepat\r\nRuangan Full AC'),(13,3,'Open Space 02',20000,'Temukan fokus dan inspirasi Anda di Open Space 08.\r\nSebuah ruang kerja bersama yang dirancang untuk kenyamanan dan produktivitas maksimal. ',1,'Active','openspace2.jpg','Durasi 2-8 Jam\r\nMeja & Kursi \r\nAkses Listrik di Setiap Meja\r\nRuangan Full AC\r\nKoneksi Wi-Fi Cepat'),(14,3,'Open Space 03',20000,'Temukan fokus dan inspirasi Anda di Open Space 03.\r\nSebuah ruang kerja bersama yang dirancang untuk kenyamanan dan produktivitas maksimal. \r\n',1,'Active','Openspace.jpg','Durasi 2-8 Jam\r\nMeja & Kursi \r\nAkses Listrik di Setiap Meja\r\nRuangan Full AC\r\nKoneksi Wi-Fi Cepat'),(15,3,'Open Space 04',20000,'Temukan fokus dan inspirasi Anda di Open Space 04.\r\nSebuah ruang kerja bersama yang dirancang untuk kenyamanan dan produktivitas maksimal. \r\n',1,'Active','Openspace.jpg','Durasi 2-8 Jam\r\nMeja & Kursi \r\nAkses Listrik di Setiap Meja\r\nRuangan Full AC\r\nKoneksi Wi-Fi Cepat'),(16,3,'Open Space 05',20000,'Temukan fokus dan inspirasi Anda di Open Space 05.\r\nSebuah ruang kerja bersama yang dirancang untuk kenyamanan dan produktivitas maksimal. \r\n',1,'Active','Openspace.jpg','Durasi 2-8 Jam\r\nMeja & Kursi \r\nAkses Listrik di Setiap Meja\r\nRuangan Full AC\r\nKoneksi Wi-Fi Cepat'),(17,3,'Open Space 06',20000,'Temukan fokus dan inspirasi Anda di Open Space 06.\r\nSebuah ruang kerja bersama yang dirancang untuk kenyamanan dan produktivitas maksimal.',1,'Active','Openspace.jpg','Durasi 2-8 Jam\r\nMeja & Kursi \r\nAkses Listrik di Setiap Meja\r\nRuangan Full AC\r\nKoneksi Wi-Fi Cepat'),(18,3,'Open Space 07',20000,'Temukan fokus dan inspirasi Anda di Open Space 07.\r\nSebuah ruang kerja bersama yang dirancang untuk kenyamanan dan produktivitas maksimal.',1,'Active','Openspace.jpg','Durasi 2-8 Jam\r\nMeja & Kursi \r\nAkses Listrik di Setiap Meja\r\nRuangan Full AC\r\nKoneksi Wi-Fi Cepat'),(19,3,'Open Space 08',20000,'Temukan fokus dan inspirasi Anda di Open Space 08.\r\nSebuah ruang kerja bersama yang dirancang untuk kenyamanan dan produktivitas maksimal. ',1,'Active','Openspace.jpg','Durasi 2-8 Jam\r\nMeja & Kursi \r\nAkses Listrik di Setiap Meja\r\nRuangan Full AC\r\nKoneksi Wi-Fi Cepat'),(20,3,'Open Space 09',20000,'Temukan fokus dan inspirasi Anda di Open Space 09.\r\nSebuah ruang kerja bersama yang dirancang untuk kenyamanan dan produktivitas maksimal.',1,'Active','Openspace.jpg','Durasi 2-8 Jam\r\nMeja & Kursi \r\nAkses Listrik di Setiap Meja\r\nRuangan Full AC\r\nKoneksi Wi-Fi Cepat'),(21,3,'Open Space 10',20000,'Temukan fokus dan inspirasi Anda di Open Space 10.\r\nSebuah ruang kerja bersama yang dirancang untuk kenyamanan dan produktivitas maksimal. ',1,'Active','openspace2.jpg','Durasi 2-8 Jam\r\nMeja & Kursi \r\nAkses Listrik di Setiap Meja\r\nRuangan Full AC\r\nKoneksi Wi-Fi Cepat'),(22,3,'Open Space 11',20000,'Temukan fokus dan inspirasi Anda di Open Space 11.\r\nSebuah ruang kerja bersama yang dirancang untuk kenyamanan dan produktivitas maksimal. ',1,'Active','openspace2.jpg','Durasi 2-8 Jam\r\nMeja & Kursi \r\nAkses Listrik di Setiap Meja\r\nRuangan Full AC\r\nKoneksi Wi-Fi Cepat'),(23,3,'Open Space 12',20000,'Temukan fokus dan inspirasi Anda di Open Space 12.\r\nSebuah ruang kerja bersama yang dirancang untuk kenyamanan dan produktivitas maksimal. ',1,'Active','openspace2.jpg','Durasi 2-8 Jam\r\nMeja & Kursi \r\nAkses Listrik di Setiap Meja\r\nRuangan Full AC\r\nKoneksi Wi-Fi Cepat'),(24,3,'Open Space 13',20000,'Temukan fokus dan inspirasi Anda di Open Space 08.\r\nSebuah ruang kerja bersama yang dirancang untuk kenyamanan dan produktivitas maksimal. ',1,'Active','openspace2.jpg','Durasi 2-8 Jam\r\nMeja & Kursi \r\nAkses Listrik di Setiap Meja\r\nRuangan Full AC\r\nKoneksi Wi-Fi Cepat'),(25,3,'Open Space 14',20000,'Temukan fokus dan inspirasi Anda di Open Space 08.\r\nSebuah ruang kerja bersama yang dirancang untuk kenyamanan dan produktivitas maksimal.',1,'Active','openspace2.jpg','Durasi 2-8 Jam\r\nMeja & Kursi \r\nAkses Listrik di Setiap Meja\r\nRuangan Full AC\r\nKoneksi Wi-Fi Cepat'),(26,6,'Ruang Meeting Kecil 02',75000,'Ciptakan sesi diskusi yang produktif dan lancar di Ruang Meeting 01. Dirancang secara profesional untuk menampung hingga 8 orang, ruangan ini menyediakan suasana yang kondusif untuk diskusi penting atau presentasi yang memukau.',4,'Active','WhatsApp_Image_2025-09-30_at_15.24.47_2be89153.jpg','Durasi 2-8 Jam\r\nSmart TV dengan port HDMI\r\nPrivate room\r\nRuangan Full AC \r\nKoneksi Wi-Fi Cepat & Stabil\r\nAkses Colokan Listrik di Area Meja'),(27,6,'Ruang Meeting Kecil 03',75000,'Minggu dan Libur Nasional tetap buka (khusus reservasi).',5,'Active','rm.jpg','Durasi 2-8 Jam\r\nSmart TV dengan port HDMI\r\nPrivate room\r\nRuangan Full AC \r\nKoneksi Wi-Fi Cepat & Stabil\r\nAkses Colokan Listrik di Area Meja'),(32,6,'Ruangan test',125000,'Test',5,'Active','Screenshot_2025-07-21-00-46-09-296_id.co.ximo.jpg','Test');
/*!40000 ALTER TABLE `ruangan` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sesi_kasir`
--

DROP TABLE IF EXISTS `sesi_kasir`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sesi_kasir` (
  `id_sesi` bigint(20) NOT NULL AUTO_INCREMENT,
  `id_user_kasir` int(11) NOT NULL COMMENT 'FK ke tabel users (role kasir)',
  `nama_sesi` varchar(255) DEFAULT NULL COMMENT 'Nama sesi cth: "Cashier 20 Okt 2025"',
  `saldo_awal` decimal(15,2) NOT NULL DEFAULT 0.00,
  `saldo_akhir_tercatat` decimal(15,2) DEFAULT NULL COMMENT 'Saldo awal + total tunai by system',
  `saldo_akhir_aktual` decimal(15,2) DEFAULT NULL COMMENT 'Uang tunai aktual yg dihitung kasir',
  `nama_kasir_penutup` varchar(255) DEFAULT NULL COMMENT 'Nama manual kasir yg menutup sesi',
  `waktu_mulai` datetime NOT NULL DEFAULT current_timestamp(),
  `waktu_selesai` datetime DEFAULT NULL,
  `status_sesi` enum('Dibuka','Ditutup') NOT NULL DEFAULT 'Dibuka',
  PRIMARY KEY (`id_sesi`),
  KEY `fk_sesi_user` (`id_user_kasir`),
  CONSTRAINT `fk_sesi_user` FOREIGN KEY (`id_user_kasir`) REFERENCES `users` (`id_user`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sesi_kasir`
--

LOCK TABLES `sesi_kasir` WRITE;
/*!40000 ALTER TABLE `sesi_kasir` DISABLE KEYS */;
INSERT INTO `sesi_kasir` VALUES (1,3,'Cashier 14 November 2025',0.00,NULL,NULL,NULL,'2025-11-14 15:39:53',NULL,'Dibuka');
/*!40000 ALTER TABLE `sesi_kasir` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `settings`
--

DROP TABLE IF EXISTS `settings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `settings` (
  `key` varchar(50) NOT NULL,
  `value` varchar(100) NOT NULL,
  `deskripsi` text DEFAULT NULL,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `settings`
--

LOCK TABLES `settings` WRITE;
/*!40000 ALTER TABLE `settings` DISABLE KEYS */;
INSERT INTO `settings` VALUES ('PAJAK_FNB_PERSEN','10','Persentase Pajak PPN untuk Makanan & Minuman');
/*!40000 ALTER TABLE `settings` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tenants`
--

DROP TABLE IF EXISTS `tenants`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tenants` (
  `id_tenant` int(11) NOT NULL AUTO_INCREMENT,
  `id_user` int(11) DEFAULT NULL,
  `nama_tenant` varchar(255) NOT NULL,
  `deskripsi_tenant` varchar(255) DEFAULT NULL,
  `gambar_tenant` varchar(255) DEFAULT 'dapoer.png',
  `status_tenant` enum('Active','Inactive') NOT NULL DEFAULT 'Active',
  PRIMARY KEY (`id_tenant`),
  KEY `id_user` (`id_user`),
  CONSTRAINT `tenants_ibfk_1` FOREIGN KEY (`id_user`) REFERENCES `users` (`id_user`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tenants`
--

LOCK TABLES `tenants` WRITE;
/*!40000 ALTER TABLE `tenants` DISABLE KEYS */;
INSERT INTO `tenants` VALUES (3,7,'Homebro','Cafe with coffee and non-coffee drinks','homebro.png','Active'),(4,8,'Dapoer M.S','food and drinks dengan cita rasa nusantara','dapoer.png','Active'),(8,37,'test_tenant3','test','c3551a73-f21d-414e-a1de-e465c766c05f_ruang-meeting.jpeg','Active');
/*!40000 ALTER TABLE `tenants` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `transaksi`
--

DROP TABLE IF EXISTS `transaksi`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `transaksi` (
  `id_transaksi` bigint(20) NOT NULL AUTO_INCREMENT,
  `id_user` int(11) DEFAULT NULL COMMENT 'NULL jika guest',
  `id_promo` int(11) DEFAULT NULL,
  `id_sesi` bigint(20) DEFAULT NULL,
  `id_kasir_pembuat` int(11) DEFAULT NULL COMMENT 'FK ke user (kasir) yg membuat transaksi',
  `subtotal` decimal(10,2) DEFAULT 0.00,
  `discount_percentage` decimal(5,2) DEFAULT 0.00,
  `pajak_persen` decimal(5,2) DEFAULT 0.00,
  `pajak_nominal` decimal(10,2) DEFAULT 0.00,
  `tanggal_transaksi` datetime NOT NULL DEFAULT current_timestamp(),
  `total_harga_final` int(11) NOT NULL,
  `metode_pembayaran` enum('Tunai','Non-Tunai') DEFAULT NULL,
  `uang_diterima` decimal(15,2) DEFAULT NULL COMMENT 'Jumlah uang tunai yg diterima',
  `kembalian` decimal(15,2) DEFAULT NULL COMMENT 'Jumlah kembalian',
  `status_pembayaran` enum('Lunas','Belum Lunas','Dibatalkan','Disimpan') NOT NULL,
  `status_order` enum('Baru','Diproses','Sebagian_diproses','Selesai','Batal') NOT NULL,
  `nama_guest` varchar(255) DEFAULT NULL,
  `lokasi_pemesanan` varchar(255) DEFAULT NULL,
  `fnb_type` enum('Dine In','Takeaway','Pick Up') DEFAULT NULL,
  `booking_source` varchar(50) DEFAULT NULL COMMENT 'Sumber booking, cth: RoomDetail, PrivateOffice, KasirWalkIn',
  PRIMARY KEY (`id_transaksi`),
  KEY `id_user` (`id_user`),
  KEY `id_promo` (`id_promo`),
  KEY `fk_transaksi_sesi` (`id_sesi`),
  KEY `fk_transaksi_kasir` (`id_kasir_pembuat`),
  CONSTRAINT `fk_transaksi_kasir` FOREIGN KEY (`id_kasir_pembuat`) REFERENCES `users` (`id_user`) ON DELETE SET NULL,
  CONSTRAINT `fk_transaksi_sesi` FOREIGN KEY (`id_sesi`) REFERENCES `sesi_kasir` (`id_sesi`) ON DELETE SET NULL,
  CONSTRAINT `transaksi_ibfk_1` FOREIGN KEY (`id_user`) REFERENCES `users` (`id_user`) ON DELETE SET NULL,
  CONSTRAINT `transaksi_ibfk_2` FOREIGN KEY (`id_promo`) REFERENCES `promo` (`id_promo`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `transaksi`
--

LOCK TABLES `transaksi` WRITE;
/*!40000 ALTER TABLE `transaksi` DISABLE KEYS */;
INSERT INTO `transaksi` VALUES (1,107,NULL,NULL,NULL,0.00,0.00,0.00,0.00,'2025-11-14 15:26:26',26000,'',NULL,NULL,'Lunas','Baru',NULL,'ruangan_4',NULL,'RoomDetail'),(2,NULL,NULL,1,3,35000.00,0.00,10.00,1500.00,'2025-11-14 15:41:42',36500,'Tunai',NULL,NULL,'Lunas','Baru','diahh','meja 5','Dine In',NULL),(3,107,NULL,NULL,NULL,0.00,0.00,0.00,0.00,'2025-11-17 09:42:56',75000,'',NULL,NULL,'Lunas','Baru',NULL,'ruangan_26',NULL,'RoomDetail'),(4,107,NULL,NULL,NULL,0.00,0.00,0.00,0.00,'2025-11-17 09:44:58',350000,'Non-Tunai',NULL,NULL,'Lunas','Baru',NULL,NULL,NULL,NULL),(5,NULL,NULL,1,71,15000.00,0.00,10.00,1500.00,'2025-11-18 09:53:32',16500,'Tunai',NULL,NULL,'Lunas','Baru','diahh','meja 5','Dine In',NULL),(6,NULL,NULL,1,3,15000.00,0.00,10.00,1500.00,'2025-11-18 14:53:57',16500,'Tunai',100000.00,100000.00,'Lunas','Baru','diahh','ruang meeting','Dine In',NULL),(7,NULL,NULL,1,3,15000.00,0.00,10.00,1500.00,'2025-11-18 14:55:56',16500,'Tunai',50000.00,50000.00,'Lunas','Baru','kasir_ruangan','os2','Dine In',NULL),(8,NULL,NULL,1,3,15000.00,0.00,10.00,1500.00,'2025-11-18 15:02:34',16500,'Tunai',100000.00,83500.00,'Lunas','Baru','diahh','meja 5','Dine In',NULL),(9,NULL,NULL,1,3,45000.00,0.00,10.00,4050.00,'2025-11-18 15:32:44',44550,'Tunai',50000.00,5450.00,'Lunas','Baru','diahh','meja 5','Dine In',NULL),(10,NULL,NULL,1,3,65000.00,5.00,10.00,4275.00,'2025-11-18 15:34:08',66025,NULL,NULL,NULL,'Disimpan','Baru','diahh','meja 5','Dine In',NULL),(11,NULL,NULL,1,3,35000.00,0.00,10.00,1500.00,'2025-11-18 15:35:28',36500,NULL,NULL,NULL,'Disimpan','Baru','diahh','meja 5','Dine In',NULL),(12,NULL,NULL,1,3,50000.00,0.00,10.00,3000.00,'2025-11-18 15:41:39',53000,'Tunai',100000.00,47000.00,'Lunas','Baru','test_saved','meja 5','Dine In',NULL),(13,NULL,NULL,1,3,15000.00,0.00,10.00,1500.00,'2025-11-19 00:31:12',16500,'Tunai',50000.00,33500.00,'Lunas','Baru','Xfsf','Dfdf','Dine In',NULL),(14,NULL,NULL,1,3,18000.00,0.00,10.00,1800.00,'2025-11-23 23:13:28',19800,'Tunai',20000.00,200.00,'Lunas','Baru','test_americano','Meja 5','Dine In',NULL);
/*!40000 ALTER TABLE `transaksi` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `users` (
  `id_user` int(11) NOT NULL AUTO_INCREMENT,
  `nama` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `password` varchar(255) NOT NULL,
  `no_telepon` varchar(20) DEFAULT NULL,
  `role` enum('admin_dago','admin_tenant','kasir','owner','pelanggan') NOT NULL DEFAULT 'pelanggan',
  `is_first_login` tinyint(1) NOT NULL DEFAULT 1 COMMENT '1=User belum ganti password default, 0=User sudah ganti password',
  PRIMARY KEY (`id_user`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `nama` (`nama`)
) ENGINE=InnoDB AUTO_INCREMENT=108 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'dwi','dwi@gmail.com','$2b$12$Qe5ZSqdfkWf8xURVI79QcubI0qByQHW1PHDwSRPjJsYRAXzNJ1GwG',NULL,'admin_dago',1),(3,'kasir','kasir@gmail.com','$2b$12$9lDu2b3uM3GMnNaxjG95pOSehHGIn3xWKmYd8cP53MxWjVbDP7c1C',NULL,'kasir',0),(4,'admindago','admindago@gmail.com','$2b$12$Q53shLmy9FAGOKFqkMZBWOIuclEoGXjIUht3S/FBKrNo3oEl69xY6',NULL,'admin_dago',1),(7,'homebro','homebro@gmail.com','$2b$12$Ea/RsX29VkI2iK19osknGuN3HGwYnP14D7zn7TbggWp7twWlt3L5C',NULL,'admin_tenant',1),(8,'dapoer','dapoer@gmail.com','$2b$12$TCWW9/UR0LWd6nrXfPC7W.AjBD6/kpWUJl4eOmzmDl22LGWqgEpW6',NULL,'admin_tenant',1),(13,'owner','owner@gmail.com','$2b$12$eFlKVT1d5Il7kV4D08pQPu6crLFenhGOAylZAeiABxmycp15YnqGe',NULL,'owner',1),(37,'test_tenant3','test_tenant3@gmail.com','$2b$12$YHnwHArkW2eZEvFvprR6F.Nie/JixdZwNPhQIHEkUqvWbhyDbC6ym',NULL,'admin_tenant',1),(71,'rose','rose@gmail.com','$2b$12$w089tfjNvBNjcgKy.d94YuDVD21lWwaLodyQ8JFmZxl6oMSxBpuk6',NULL,'kasir',0),(77,'sapta','sapta@gmail.com','$2b$12$dxmWFWBI2EOjD4Y4uvR5EuCRB/rW.G9ZUbndJPk/BACXWzGFWtULa',NULL,'kasir',0),(79,'adit','adit@gmail.com','$2b$12$nj89zw3zxfrCiAQlLV2cjOSLTVI0ktOdbJN0iOw/tCaFIYdaZnmVK',NULL,'admin_tenant',1),(82,'kasir1234','kasir1234@gmail.com','$2b$12$nIrNE1lnCMywayl99Ix.vuSv4fyDIdZPm2BSZnIhntSxIhU.iWt9u',NULL,'kasir',0),(83,'dea','dea@gmail.com','$2b$12$jdtq.j06JZVVsPkbsFpDeOX6u18r3h74JmE3XcHgnmbzAl48bzqUy',NULL,'kasir',0),(86,'kasir_test','kasir_test@gmail.com','$2b$12$xOSvuQa6W.7EPJl4kfZpLuySP9TQUTXq9vM8goWf2ZffSuEeyOyRG',NULL,'kasir',0),(94,'Incess rossa','incessx.aloy@gmail.com','$2b$12$YVbaTDANWaq0UBxIMJ2Vj.HgUaE3HkcaXD1aQkf3ShZNv86wbFxti',NULL,'admin_tenant',1),(105,'kasir_izy','kasir_izy@gmail.com','$2b$12$uE6fPJGwLmeAHJkTAoJw0OLEGFcVhU/nNE8y4ExBhpsZ7chSTkIxy',NULL,'kasir',0),(106,'mardial','mardial@gmail.com','$2b$12$g/uw8ZAMPiGW3mPB2DVSRO63gcAujXLHTxmRkz5xx0qHX0NVFRCS2',NULL,'kasir',0),(107,'diah','diah@gmail.com','$2b$12$C3WRzuY44jdgrZeVSe3guuW7xC8WlCIXCn9wdyB2GpSKe9vPDYQXq',NULL,'pelanggan',1);
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `utang_tenant`
--

DROP TABLE IF EXISTS `utang_tenant`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `utang_tenant` (
  `id_utang` bigint(20) NOT NULL AUTO_INCREMENT,
  `id_tenant` int(11) NOT NULL,
  `tanggal_utang` date NOT NULL,
  `jumlah` decimal(10,2) NOT NULL DEFAULT 0.00,
  `deskripsi` text DEFAULT NULL,
  `status_lunas` tinyint(1) NOT NULL DEFAULT 0,
  `id_rekap_pelunasan` int(11) DEFAULT NULL COMMENT 'FK opsional ke rekap_bagi_hasil saat utang ini dilunasi',
  PRIMARY KEY (`id_utang`),
  KEY `id_tenant` (`id_tenant`),
  KEY `id_rekap_pelunasan` (`id_rekap_pelunasan`),
  CONSTRAINT `utang_tenant_ibfk_1` FOREIGN KEY (`id_tenant`) REFERENCES `tenants` (`id_tenant`) ON DELETE CASCADE,
  CONSTRAINT `utang_tenant_ibfk_2` FOREIGN KEY (`id_rekap_pelunasan`) REFERENCES `rekap_bagi_hasil` (`id_rekap_bagi_hasil`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `utang_tenant`
--

LOCK TABLES `utang_tenant` WRITE;
/*!40000 ALTER TABLE `utang_tenant` DISABLE KEYS */;
INSERT INTO `utang_tenant` VALUES (1,4,'2025-11-14',1000.00,'bon',0,NULL);
/*!40000 ALTER TABLE `utang_tenant` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-11-23 23:35:38
