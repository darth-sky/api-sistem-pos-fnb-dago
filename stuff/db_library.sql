-- MySQL dump 10.13  Distrib 8.3.0, for macos14.2 (x86_64)
--
-- Host: 127.0.0.1    Database: db_library
-- ------------------------------------------------------
-- Server version	8.3.0

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `tb_books`
--

DROP TABLE IF EXISTS `tb_books`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tb_books` (
  `id_books` int NOT NULL AUTO_INCREMENT COMMENT 'incremental ID for table tb_books',
  `title` varchar(225) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT 'Books title',
  `description` tinytext COLLATE utf8mb4_general_ci,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Book created at',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_books`)
) ENGINE=InnoDB AUTO_INCREMENT=34 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tb_books`
--

LOCK TABLES `tb_books` WRITE;
/*!40000 ALTER TABLE `tb_books` DISABLE KEYS */;
INSERT INTO `tb_books` VALUES (1,'Harry potter edit','update description updated','2024-04-02 04:32:11','2024-04-02 04:32:11'),(2,'Romeo and Juliet',NULL,'2024-04-02 04:33:01','2024-04-02 04:33:01'),(3,'House of Flame and Shadow',NULL,'2024-04-02 04:33:54','2024-04-02 04:33:54'),(4,'Fourth Wing',NULL,'2024-04-02 04:34:13','2024-04-02 04:34:13'),(5,'Iron Flame',NULL,'2024-04-02 04:34:29','2024-04-02 04:34:29'),(6,'It Ends with us',NULL,'2024-04-02 04:36:52','2024-04-02 04:36:52'),(7,'Bride',NULL,'2024-04-02 04:36:52','2024-04-02 04:36:52'),(8,'Harry Potter Philosopher\'s Stone',NULL,'2024-04-02 04:36:52','2024-04-02 04:36:52'),(9,'Harry Potter Chamber of Secrets ',NULL,'2024-04-02 04:36:52','2024-04-02 04:36:52'),(10,'Harry Potter Prisoner of Azkaban',NULL,'2024-04-02 04:36:52','2024-04-02 04:36:52'),(11,'Harry Potter Goblet of File',NULL,'2024-04-02 04:36:52','2024-04-02 04:36:52'),(12,'Harry Potter Half Blood Prince',NULL,'2024-04-02 04:36:52','2024-04-02 04:36:52'),(13,'Harry Potter Deathly Hallows',NULL,'2024-04-02 04:36:52','2024-04-02 04:36:52'),(29,'update title books test','update description updated','2024-05-14 15:12:08','2024-05-14 15:12:08'),(31,'test','delete books','2024-05-14 15:15:10','2024-05-14 15:15:10'),(32,'test','delete books','2024-05-15 00:53:10','2024-05-15 00:53:10'),(33,'test book harry potter','description book harry potter','2024-05-15 04:48:29','2024-05-15 04:48:29');
/*!40000 ALTER TABLE `tb_books` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id_users` int NOT NULL AUTO_INCREMENT,
  `username` varchar(255) NOT NULL,
  `password` varchar(225) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `deleted_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id_users`),
  UNIQUE KEY `users_pk` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'john_doe','$2b$12$6bzZ3QZjTsMQ2xYmFijOKeGmu5JjeV5sb6LHkFOIOWObWL8dQy70S','2024-05-29 07:35:50','2024-05-29 07:35:50',NULL),(2,'jean_doe','$2b$12$Ywex3fWuHj0H90BztX7DieUvd6VHYHtu5LD8hxabL35f5WmSq3zp.','2024-05-29 07:38:50','2024-05-29 07:38:50',NULL);
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2024-05-29 18:02:12
